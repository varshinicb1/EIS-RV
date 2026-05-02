import React, { useState, useEffect, useCallback } from 'react';
import { useTheme } from '../../hooks/useTheme';

export default function UserProfilePanel() {
  const { theme, setTheme, themes } = useTheme();
  const [profile, setProfile] = useState({
    name: 'Dr. Varshini C.B.',
    email: 'varshini@vidyuthlabs.com',
    organization: 'VidyuthLabs Pvt. Ltd.',
    role: 'Principal Investigator',
    department: 'Electrochemistry & Nanomaterials',
    orcid: '0000-0001-2345-6789',
  });
  const [license, setLicense] = useState({
    type: 'Enterprise', key: 'RMNS-VIDYUTH-ENT-2026', status: 'active',
    expiry: '2027-05-01', seats: 10, usedSeats: 3,
    features: ['EIS','CV','Battery','DRT','GCD','Circuit Fit','Biosensor','Alchemi AI','Literature Mining','PDF Export'],
  });
  const [saved, setSaved] = useState(false);
  const [licenseInput, setLicenseInput] = useState('');
  const [notifications, setNotifications] = useState({ emailDigest: true, simulationComplete: true, systemAlerts: true, weeklyReport: false });

  useEffect(() => {
    try {
      const sp = localStorage.getItem('raman-profile');
      if (sp) setProfile(JSON.parse(sp));
      const sl = localStorage.getItem('raman-license');
      if (sl) setLicense(JSON.parse(sl));
    } catch {}
  }, []);

  const handleSave = useCallback(() => {
    try {
      localStorage.setItem('raman-profile', JSON.stringify(profile));
      localStorage.setItem('raman-license', JSON.stringify(license));
    } catch {}
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }, [profile, license]);

  const activateLicense = () => {
    if (!licenseInput.startsWith('RMNS-')) return;
    setLicense(p => ({ ...p, key: licenseInput, status: 'active', expiry: '2028-01-01' }));
    setLicenseInput('');
  };

  const updateField = (f, v) => setProfile(p => ({ ...p, [f]: v }));
  const sty = { section: { background: 'var(--bg-elevated)', borderRadius: 8, border: '1px solid var(--border-primary)', marginBottom: 12, padding: 16 },
    row: { display: 'flex', alignItems: 'center', gap: 12, padding: '8px 0', borderBottom: '1px solid var(--border-primary)' },
    lbl: { width: 120, fontSize: 11, fontWeight: 500, color: 'var(--text-secondary)', flexShrink: 0 } };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, height: '100%', overflow: 'auto', padding: 2 }} className="animate-in">
      <div>
        {/* Avatar Card */}
        <div style={{ ...sty.section, display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ width: 56, height: 56, borderRadius: 14, background: 'linear-gradient(135deg, var(--accent), #76b900)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, fontWeight: 700, color: '#000' }}>
            {profile.name?.split(' ').map(n => n[0]).join('').slice(0, 2)}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>{profile.name}</div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{profile.role} · {profile.organization}</div>
          </div>
          <span style={{ padding: '3px 8px', borderRadius: 4, fontSize: 9, fontWeight: 600, background: 'rgba(118,185,0,0.12)', color: '#76b900', border: '1px solid #76b90033' }}>{license.type}</span>
        </div>

        {/* Personal Info */}
        <div style={sty.section}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 10 }}>Personal Information</div>
          {[['name','Full Name'],['email','Email'],['organization','Organization'],['role','Role'],['department','Department'],['orcid','ORCID']].map(([k,l]) => (
            <div key={k} style={sty.row}>
              <span style={sty.lbl}>{l}</span>
              <input className="input-field" value={profile[k]} onChange={e => updateField(k, e.target.value)} style={{ flex: 1, fontSize: 12 }} />
            </div>
          ))}
        </div>

        {/* Notifications */}
        <div style={sty.section}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 10 }}>Notifications</div>
          {Object.entries(notifications).map(([k, v]) => (
            <div key={k} style={{ ...sty.row, cursor: 'pointer' }} onClick={() => setNotifications(n => ({ ...n, [k]: !v }))}>
              <span style={{ flex: 1, fontSize: 11, color: 'var(--text-secondary)', textTransform: 'capitalize' }}>{k.replace(/([A-Z])/g, ' $1')}</span>
              <div style={{ width: 32, height: 16, borderRadius: 8, padding: 2, background: v ? 'var(--accent)' : 'var(--bg-primary)', border: `1px solid ${v ? 'transparent' : 'var(--border-secondary)'}`, transition: 'all 0.2s' }}>
                <div style={{ width: 12, height: 12, borderRadius: 6, background: v ? '#000' : 'var(--text-tertiary)', transform: v ? 'translateX(14px)' : 'translateX(0)', transition: 'transform 0.2s' }} />
              </div>
            </div>
          ))}
        </div>
      </div>

      <div>
        {/* License */}
        <div style={sty.section}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 10 }}>License Management</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
            <div style={{ background: 'var(--bg-primary)', borderRadius: 6, padding: 10, border: '1px solid var(--border-primary)' }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: '#76b900' }}>{license.type}</div>
              <div style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>License Tier</div>
            </div>
            <div style={{ background: 'var(--bg-primary)', borderRadius: 6, padding: 10, border: '1px solid var(--border-primary)' }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--accent)' }}>{license.usedSeats}/{license.seats}</div>
              <div style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>Active Seats</div>
            </div>
          </div>
          {[['Key', license.key],['Status', license.status.toUpperCase()],['Expires', license.expiry]].map(([l,v]) => (
            <div key={l} style={sty.row}><span style={sty.lbl}>{l}</span><span style={{ fontSize: 11, color: l==='Status' ? '#76b900' : 'var(--text-secondary)', fontFamily: 'var(--font-data)' }}>{v}</span></div>
          ))}
          <div style={{ marginTop: 8 }}>
            <span style={sty.lbl}>Features</span>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
              {license.features.map(f => <span key={f} style={{ padding: '2px 6px', borderRadius: 3, fontSize: 9, background: 'var(--accent-muted)', color: 'var(--accent)', border: '1px solid var(--accent-border)' }}>{f}</span>)}
            </div>
          </div>
          <div style={{ marginTop: 12, display: 'flex', gap: 6 }}>
            <input className="input-field" placeholder="RMNS-..." value={licenseInput} onChange={e => setLicenseInput(e.target.value)} style={{ flex: 1, fontSize: 11 }} />
            <button className="btn btn-sm btn-primary" onClick={activateLicense} style={{ fontSize: 11 }}>Activate</button>
          </div>
        </div>

        {/* Theme */}
        <div style={sty.section}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 10 }}>Theme</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6 }}>
            {Object.entries(themes).map(([id, t]) => (
              <button key={id} onClick={() => setTheme(id)} style={{ background: theme===id ? 'var(--accent-muted)' : 'var(--bg-primary)', border: `2px solid ${theme===id ? 'var(--accent)' : 'var(--border-primary)'}`, borderRadius: 6, padding: 8, cursor: 'pointer', textAlign: 'center', transition: 'all 0.2s' }}>
                <div style={{ display: 'flex', justifyContent: 'center', gap: 3, marginBottom: 4 }}>
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: t.vars['--bg-primary'], border: '1px solid #444' }} />
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: t.vars['--accent'] }} />
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: t.vars['--text-primary'], border: '1px solid #444' }} />
                </div>
                <div style={{ fontSize: 9, fontWeight: 600, color: theme===id ? 'var(--accent)' : 'var(--text-primary)' }}>{t.label}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Save */}
        <button className="btn btn-primary" onClick={handleSave} style={{ width: '100%', marginTop: 8, background: saved ? '#76b900' : 'linear-gradient(135deg, var(--accent), #76b900)', transition: 'all 0.3s' }}>
          {saved ? '✓ Saved' : 'Save All Changes'}
        </button>
      </div>
    </div>
  );
}
