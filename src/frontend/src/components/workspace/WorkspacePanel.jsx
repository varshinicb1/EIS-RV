import React, { useState, useEffect, useCallback } from 'react';

const PROJECT_TEMPLATES = [
  { id: 'eis-study', name: 'EIS Study', icon: '📊', desc: 'Impedance analysis with Randles circuit' },
  { id: 'biosensor', name: 'Biosensor Design', icon: '🧬', desc: 'Electrode fabrication & analyte detection' },
  { id: 'battery', name: 'Battery Analysis', icon: '🔋', desc: 'SPM modeling & charge-discharge' },
  { id: 'materials', name: 'Materials Discovery', icon: '⚛️', desc: 'AI-powered material exploration' },
  { id: 'custom', name: 'Custom Project', icon: '📁', desc: 'Blank workspace' },
];

export default function WorkspacePanel() {
  const [projects, setProjects] = useState([]);
  const [activeProject, setActiveProject] = useState(null);
  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState('');
  const [newTemplate, setNewTemplate] = useState('custom');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    try {
      const saved = localStorage.getItem('raman-projects');
      if (saved) {
        const parsed = JSON.parse(saved);
        setProjects(parsed);
        if (parsed.length > 0) setActiveProject(parsed[0].id);
      }
    } catch {}
  }, []);

  const saveProjects = useCallback((p) => {
    try { localStorage.setItem('raman-projects', JSON.stringify(p)); } catch {}
  }, []);

  const createProject = () => {
    if (!newName.trim()) return;
    const proj = {
      id: `proj_${Date.now()}`,
      name: newName,
      template: newTemplate,
      created: new Date().toISOString(),
      modified: new Date().toISOString(),
      status: 'active',
      simulations: [],
      notes: '',
      tags: [newTemplate],
    };
    const updated = [proj, ...projects];
    setProjects(updated);
    saveProjects(updated);
    setActiveProject(proj.id);
    setShowNew(false);
    setNewName('');
  };

  const deleteProject = (id) => {
    const updated = projects.filter(p => p.id !== id);
    setProjects(updated);
    saveProjects(updated);
    if (activeProject === id) setActiveProject(updated[0]?.id || null);
  };

  const duplicateProject = (id) => {
    const orig = projects.find(p => p.id === id);
    if (!orig) return;
    const dup = { ...orig, id: `proj_${Date.now()}`, name: `${orig.name} (Copy)`, created: new Date().toISOString(), modified: new Date().toISOString() };
    const updated = [dup, ...projects];
    setProjects(updated);
    saveProjects(updated);
  };

  const updateNotes = (id, notes) => {
    const updated = projects.map(p => p.id === id ? { ...p, notes, modified: new Date().toISOString() } : p);
    setProjects(updated);
    saveProjects(updated);
  };

  const filtered = projects.filter(p => p.name.toLowerCase().includes(searchQuery.toLowerCase()));
  const active = projects.find(p => p.id === activeProject);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 14, height: '100%' }} className="animate-in">
      {/* Project List */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div className="card-header">
          <div>
            <div className="card-title">Projects</div>
            <div className="card-subtitle">{projects.length} total</div>
          </div>
          <button className="btn btn-sm btn-primary" onClick={() => setShowNew(true)} style={{ fontSize: 11 }}>+ New</button>
        </div>

        <div style={{ padding: '0 12px 8px' }}>
          <input className="input-field" placeholder="Search projects..." value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)} style={{ fontSize: 11 }} />
        </div>

        <div style={{ flex: 1, overflow: 'auto', padding: '0 12px 12px' }}>
          {filtered.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 30, color: 'var(--text-disabled)', fontSize: 11 }}>
              {projects.length === 0 ? 'No projects yet. Create one to get started.' : 'No matching projects.'}
            </div>
          ) : filtered.map(p => (
            <div key={p.id} onClick={() => setActiveProject(p.id)}
              style={{
                padding: '10px 12px', borderRadius: 6, marginBottom: 4, cursor: 'pointer',
                background: activeProject === p.id ? 'var(--accent-muted)' : 'transparent',
                border: `1px solid ${activeProject === p.id ? 'var(--accent-border)' : 'transparent'}`,
                transition: 'all 0.15s',
              }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 16 }}>{PROJECT_TEMPLATES.find(t => t.id === p.template)?.icon || '📁'}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{p.name}</div>
                  <div style={{ fontSize: 9, color: 'var(--text-tertiary)', marginTop: 2 }}>
                    {new Date(p.modified).toLocaleDateString()} · {p.simulations?.length || 0} simulations
                  </div>
                </div>
                <span style={{ width: 6, height: 6, borderRadius: 3, background: p.status === 'active' ? 'var(--color-success)' : 'var(--color-warning)' }} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Project Detail / New Project */}
      {showNew ? (
        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="card-header">
            <div className="card-title">New Project</div>
            <button className="btn btn-sm btn-ghost" onClick={() => setShowNew(false)}>Cancel</button>
          </div>
          <div style={{ padding: 16 }}>
            <div className="input-group">
              <span className="input-label">Project Name</span>
              <input className="input-field" value={newName} onChange={e => setNewName(e.target.value)} placeholder="My Research Project" autoFocus />
            </div>
            <div className="input-group" style={{ marginTop: 12 }}>
              <span className="input-label">Template</span>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginTop: 6 }}>
                {PROJECT_TEMPLATES.map(t => (
                  <button key={t.id} onClick={() => setNewTemplate(t.id)}
                    style={{
                      background: newTemplate === t.id ? 'var(--accent-muted)' : 'var(--bg-primary)',
                      border: `2px solid ${newTemplate === t.id ? 'var(--accent)' : 'var(--border-primary)'}`,
                      borderRadius: 8, padding: 12, cursor: 'pointer', textAlign: 'center', transition: 'all 0.2s',
                    }}>
                    <div style={{ fontSize: 20, marginBottom: 4 }}>{t.icon}</div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-primary)' }}>{t.name}</div>
                    <div style={{ fontSize: 9, color: 'var(--text-tertiary)', marginTop: 2 }}>{t.desc}</div>
                  </button>
                ))}
              </div>
            </div>
            <button className="btn btn-primary" onClick={createProject} disabled={!newName.trim()}
              style={{ width: '100%', marginTop: 16 }}>
              Create Project
            </button>
          </div>
        </div>
      ) : active ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Project Header */}
          <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 14, padding: 16 }}>
            <span style={{ fontSize: 32 }}>{PROJECT_TEMPLATES.find(t => t.id === active.template)?.icon || '📁'}</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' }}>{active.name}</div>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>
                Created {new Date(active.created).toLocaleDateString()} · Modified {new Date(active.modified).toLocaleDateString()}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <button className="btn btn-sm btn-ghost" onClick={() => duplicateProject(active.id)}>Duplicate</button>
              <button className="btn btn-sm" onClick={() => deleteProject(active.id)}
                style={{ background: 'rgba(239,83,80,0.1)', color: 'var(--color-error)', border: '1px solid #ef535033' }}>Delete</button>
            </div>
          </div>

          {/* Stats & Notes */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
            {[
              ['Simulations', active.simulations?.length || 0, '#4a9eff'],
              ['Status', active.status, 'var(--color-success)'],
              ['Template', active.template?.replace(/-/g, ' '), 'var(--color-warning)'],
            ].map(([l, v, c]) => (
              <div key={l} className="card" style={{ textAlign: 'center', padding: 14 }}>
                <div style={{ fontSize: 20, fontWeight: 700, color: c, fontFamily: 'var(--font-data)', textTransform: 'capitalize' }}>{v}</div>
                <div style={{ fontSize: 9, color: 'var(--text-tertiary)', marginTop: 2 }}>{l}</div>
              </div>
            ))}
          </div>

          {/* Notes */}
          <div className="card" style={{ flex: 1 }}>
            <div className="card-title" style={{ marginBottom: 8 }}>Research Notes</div>
            <textarea className="input-field" value={active.notes || ''} onChange={e => updateNotes(active.id, e.target.value)}
              placeholder="Add research notes, observations, and hypotheses..."
              style={{ width: '100%', height: 200, resize: 'vertical', fontSize: 12, lineHeight: 1.6, fontFamily: 'Inter, sans-serif' }} />
          </div>
        </div>
      ) : (
        <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ textAlign: 'center', color: 'var(--text-disabled)' }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>📁</div>
            <div style={{ fontSize: 13 }}>Create or select a project</div>
          </div>
        </div>
      )}
    </div>
  );
}
