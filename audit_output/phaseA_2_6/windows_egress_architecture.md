# Phase A.2.6 — Windows Host-Level Egress Architecture

**Project:** AgentDesk  
**Target Path:** `C:\Users\azize\source\AgentDesk`  
**Phase:** A.2.6 — Windows Host-Level Egress Enforcement  
**Audit Date:** 2026-11-09  
**Auditor:** Independent Adversarial Security Agent  

---

## 1. Executive Summary

Phase A.2.5 established that while application-layer isolation through `SecureEgressProxy` is robust, resilient, and fails closed under adversarial conditions, Windows Defender Firewall on the host operating system contains zero outbound blocking rules (operating under a default `Allow` policy). 

This report presents an architectural investigation of Windows-native network containment options to determine how host-level network egress enforcement can be established for Playwright Chromium without disrupting the desktop application's workflow or destabilizing system-wide networking.

---

## 2. Evaluation of Windows-Native Enforcement Mechanisms

Five distinct architectural approaches for host-level network egress control on Windows were evaluated:

```
+--------------------------------------------------------------------------------------------------+
|                                    WINDOWS ENFORCEMENT OPTIONS                                   |
+--------------------------------------------------------------------------------------------------+
| 1. Windows Defender Firewall (WFAS) Application Rules                                            |
|    - Operates at application binary path level (chrome.exe).                                     |
|    - Rule precedence: BLOCK unconditionally overrides ALLOW.                                     |
|    - Privilege boundary: Requires Administrator elevation (High Mandatory Level).                |
|    - Dynamic Port Limitation: Cannot track ephemeral proxy ports without active daemon.          |
+--------------------------------------------------------------------------------------------------+
| 2. Windows Filtering Platform (WFP) ALE Connect Filters                                         |
|    - Operates at kernel ALE layer (FWPM_LAYER_ALE_AUTH_CONNECT_V4/V6).                           |
|    - Allows fine-grained numerical filter weights (ALLOW can override BLOCK in custom sublayer). |
|    - Privilege boundary: Requires Administrator / SYSTEM elevation and signed kernel/WFP code.   |
|    - Safety risk: Kernel-level filters risk system-wide network disconnection if unhandled.      |
+--------------------------------------------------------------------------------------------------+
| 3. Elevated Windows Background Service                                                           |
|    - Dedicated service running as NT AUTHORITY\SYSTEM.                                           |
|    - Dynamically configures firewall or WFP rules via IPC from AgentDesk.                        |
|    - Privilege boundary: Requires UAC administrative approval during installer execution.        |
+--------------------------------------------------------------------------------------------------+
| 4. AppContainer Sandboxing                                                                       |
|    - Capability-based isolation (omits internetClient capability).                               |
|    - Restricts public egress, but also blocks loopback (127.0.0.1) by default.                   |
|    - Loopback exemption requires CheckNetIsolation.exe LoopbackExempt (requires Administrator).  |
|    - Breaks Playwright DevTools Protocol (CDP) pipe without elevated configuration.             |
+--------------------------------------------------------------------------------------------------+
| 5. Hardened Application Proxy Gateway (Current Phase A.2.4 Baseline)                             |
|    - Loopback proxy (127.0.0.1) with dynamic 24-byte Basic authentication.                      |
|    - Chromium CLI flags: --proxy-server, --proxy-bypass-list=<-loopback>, --disable-webrtc.      |
|    - Fails closed immediately (net::ERR_PROXY_CONNECTION_FAILED) if proxy is unavailable.       |
|    - Privilege boundary: Fully operable under Standard User (Medium Mandatory Level).            |
+--------------------------------------------------------------------------------------------------+
```

---

## 3. Deep Architectural Analysis

### 3.1 Windows Defender Firewall (WFAS / NetSecurity)
- **Privilege Boundary:**
  In Windows 11, invoking `New-NetFirewallRule` or modifying the AdvFirewall engine requires membership in `BUILTIN\Administrators` and High Mandatory Level (elevated token). When executed from a standard desktop session (Medium Mandatory Level), PowerShell cmdlets fail immediately with `Access is denied.` (Win32 Error 5).
- **Rule Precedence Trap:**
  Windows Defender Firewall enforces a strict rule evaluation hierarchy where **Block rules always supersede Allow rules**. An administrator attempting to "Block all outbound for `chrome.exe`" and simultaneously "Allow `127.0.0.1` for `chrome.exe`" will discover that the Block rule matches first, dropping all traffic including loopback connections to `SecureEgressProxy`.
- **Dynamic Port Impedance:**
  `SecureEgressProxy` binds to an ephemeral loopback port (`127.0.0.1:<random_port>`) at startup to prevent port collisions with other development tools. A static Windows Firewall rule cannot predict this port. Re-creating firewall rules on every application launch would require an elevated UAC prompt on every startup, which is unacceptable for a desktop application.

### 3.2 Windows Filtering Platform (WFP)
- **Kernel Mechanism:**
  WFP ALE (Application Layer Enforcement) inspects network connections at `FWPM_LAYER_ALE_AUTH_CONNECT_V4` and `FWPM_LAYER_ALE_AUTH_CONNECT_V6`.
- **Feasibility:**
  Unlike WFAS, WFP filters can use weighted sublayers where an explicit Allow filter on loopback has higher weight than an outbound Block filter.
- **Limitation:**
  Managing WFP sessions via `FwpmEngineOpen0` and `FwpmFilterAdd0` requires administrative privileges (`SE_DEBUG_NAME` or local admin). Furthermore, running custom WFP code in user mode from a desktop app introduces stability risks: if the desktop app crashes or terminates abruptly, orphaned WFP filters can permanently break host internet access until a reboot or manual netsh reset.

### 3.3 AppContainer Network Isolation
- **Mechanism:**
  Windows AppContainers isolate processes by security identifiers (SIDs). Network access is controlled by capabilities:
  - `internetClient` (public outbound)
  - `privateNetworkClientServer` (intranet / LAN outbound)
- **Loopback Isolation:**
  To prevent sandboxed apps from exploiting local network services, Windows kernel blocks AppContainers from accessing `127.0.0.1` unless an exemption is registered via `CheckNetIsolation.exe LoopbackExempt -a -n=<ContainerSID>`.
- **Limitation:**
  `CheckNetIsolation.exe` requires administrative privileges. Furthermore, Playwright communicates with Chromium via internal pipes or WebSocket control sockets; placing the parent Chromium browser into an AppContainer without extensive OS capabilities causes Playwright initialization to hang or crash.

---

## 4. Proposed Production Deployment Architecture

To achieve true host-level packet enforcement in a production release without compromising runtime user experience, the enforcement must be split between **Installer Time** (Elevated) and **Runtime** (Unprivileged):

```
========================================================================================
INSTALLER TIME (Elevated - WiX / NSIS MSI Installer)
========================================================================================
1. Installer requests UAC elevation once during installation.
2. Installer registers a static loopback proxy reservation port (e.g., 58399).
3. Installer provisions a dedicated Windows Firewall Rule:
   - Rule Name: "AgentDesk Scraper Network Egress Block"
   - Direction: Outbound
   - Program: "%LOCALAPPDATA%\ms-playwright\chromium-*\chrome-win64\chrome.exe"
   - Action: Block
   - RemoteAddress: 1.0.0.0-126.255.255.255, 128.0.0.0-255.255.255.255, 127.0.0.2-127.255.255.255
4. Installer creates a companion rule allowing strictly 127.0.0.1:58399.

========================================================================================
APPLICATION RUNTIME (Standard User - Medium Integrity)
========================================================================================
1. AgentDesk starts as a standard unprivileged user application.
2. SecureEgressProxy binds to the pre-allocated port (e.g., 58399) on 127.0.0.1.
3. Playwright launches Chromium with:
   --proxy-server=http://127.0.0.1:58399
   --proxy-bypass-list=<-loopback>
   --disable-webrtc
4. Multi-Layer Defense:
   - Layer 1 (OS Kernel): Windows Firewall drops any direct public/LAN packet from chrome.exe.
   - Layer 2 (Browser Engine): Chromium CLI flags route all requests through proxy.
   - Layer 3 (Proxy Gateway): Dynamic auth + SSRF/DNS pinning + fail-closed validation.
========================================================================================
```

---

## 5. Architectural Conclusion

In the current development environment, AgentDesk executes under standard user privileges (Medium Mandatory Level). Attempting to mutate Windows Defender Firewall or WFP rules at runtime without administrative elevation triggers `Access is denied.`

Therefore, application-level isolation via `SecureEgressProxy` represents the maximum safe security boundary achievable at runtime without administrative elevation. Full host-level firewall enforcement must be packaged as an installer-time deployment capability.

