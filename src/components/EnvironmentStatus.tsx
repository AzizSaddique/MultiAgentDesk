import { AlertTriangleIcon, CheckCircleIcon, TerminalIcon } from './icons';
import { BackendStatus } from '../hooks/useBackendStatus';

interface EnvironmentStatusProps {
  backendStatus?: BackendStatus;
}

export const EnvironmentStatus: React.FC<EnvironmentStatusProps> = ({ backendStatus }) => {
  return (
    <div className="dashboard-viewport">
      {/* Alert Header */}
      <div className="env-alert-box">
        <div className="env-alert-header">
          <AlertTriangleIcon size={20} color="#fbbf24" />
          <span>Action Required for Tauri Native Desktop Compilation</span>
        </div>
        <p className="env-alert-text">
          Frontend files and Vite development server are fully ready. However, building or running the native Windows binary via Tauri requires the Microsoft C++ Build Tools (MSVC Linker <code>link.exe</code>) and the Windows 10/11 SDK.
        </p>
      </div>

      {/* Verification Matrix */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">
            <CheckCircleIcon size={18} color="var(--accent-cyan)" />
            Environment & Prerequisite Audit
          </h3>
          <span className="badge badge-warning">1 Action Required</span>
        </div>

        <table className="env-table">
          <thead>
            <tr style={{ textAlign: 'left', color: 'var(--text-muted)', borderBottom: '1px solid var(--border-subtle)' }}>
              <th style={{ padding: '0.5rem' }}>Component</th>
              <th style={{ padding: '0.5rem' }}>Detected Status</th>
              <th style={{ padding: '0.5rem' }}>Version / Location</th>
              <th style={{ padding: '0.5rem' }}>Assessment</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>FastAPI Microservice</strong></td>
              <td>
                <span className={`badge ${backendStatus?.isOnline ? 'badge-active' : 'badge-offline'}`}>
                  <span className="badge-dot" /> {backendStatus?.isOnline ? 'Online' : 'Offline'}
                </span>
              </td>
              <td>http://127.0.0.1:8000</td>
              <td>
                {backendStatus?.isOnline
                  ? `${backendStatus.data?.service || 'AgentDesk API'} (${backendStatus.data?.status || 'ok'})`
                  : 'Backend offline (run start-backend.ps1)'}
              </td>
            </tr>
            <tr>
              <td><strong>Node.js</strong></td>
              <td><span className="badge badge-active"><span className="badge-dot" /> Ready</span></td>
              <td>v24.6.0</td>
              <td>Confirmed and functioning</td>
            </tr>
            <tr>
              <td><strong>npm</strong></td>
              <td><span className="badge badge-active"><span className="badge-dot" /> Ready</span></td>
              <td>11.5.1</td>
              <td>Confirmed and functioning</td>
            </tr>
            <tr>
              <td><strong>Python</strong></td>
              <td><span className="badge badge-active"><span className="badge-dot" /> Ready</span></td>
              <td>3.13.5</td>
              <td>Confirmed (FastAPI & Uvicorn installed)</td>
            </tr>
            <tr>
              <td><strong>WebView2 Runtime</strong></td>
              <td><span className="badge badge-active"><span className="badge-dot" /> Ready</span></td>
              <td>155.0.4283.45</td>
              <td>Installed (C:\Program Files (x86)\Microsoft\EdgeWebView)</td>
            </tr>
            <tr>
              <td><strong>Rust Toolchain</strong></td>
              <td><span className="badge badge-warning">PATH Notice</span></td>
              <td>rustc / cargo 1.99.1</td>
              <td>Installed in %USERPROFILE%\.cargo\bin; Needs PATH in shell</td>
            </tr>
            <tr>
              <td><strong>MSVC C++ Build Tools (link.exe)</strong></td>
              <td><span className="badge badge-warning">Missing Linker</span></td>
              <td>link.exe not found</td>
              <td>VS Community 2022 setup canceled/incomplete (state: 5, canceled: 1)</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Manual Remediation Steps */}
      <div className="grid-cols-2">
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">
              <TerminalIcon size={16} color="var(--accent-cyan)" />
              Step 1: Install MSVC C++ Build Tools
            </h3>
          </div>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '0.75rem', lineHeight: 1.5 }}>
            To enable Rust MSVC toolchain to link native Windows executables:
          </p>
          <ol style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', paddingLeft: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
            <li>Open the <strong>Visual Studio Installer</strong> on your Windows PC.</li>
            <li>Select <strong>Visual Studio Community 2022</strong> (or Build Tools) and click <strong>Modify</strong>.</li>
            <li>Check the workload: <strong>Desktop development with C++</strong>.</li>
            <li>Ensure <strong>MSVC v143 - VS 2022 C++ x64/x86 build tools</strong> and <strong>Windows 10/11 SDK</strong> are checked in optional details.</li>
            <li>Click <strong>Install / Resume</strong> and let the installation complete.</li>
          </ol>
        </div>

        <div className="card">
          <div className="card-header">
            <h3 className="card-title">
              <TerminalIcon size={16} color="var(--accent-indigo)" />
              Step 2: Ensure Cargo is in Terminal PATH
            </h3>
          </div>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '0.75rem', lineHeight: 1.5 }}>
            Rust is already installed under your user profile. In PowerShell or System Environment Variables:
          </p>
          <div className="code-box" style={{ marginBottom: '0.75rem' }}>
            $env:PATH += ";$env:USERPROFILE\.cargo\bin"
          </div>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Or restart your terminal session after verifying that <code>C:\Users\azize\.cargo\bin</code> is listed in your User Environment PATH.
          </p>
        </div>
      </div>
    </div>
  );
};
