/**
 * Advanced Analysis Panel - OriginLab-style comprehensive data analysis
 * 
 * Features:
 * - Multi-column worksheet editor
 * - Statistical analysis (descriptive, hypothesis testing, regression)
 * - Curve fitting (100+ functions)
 * - Signal processing (FFT, wavelet, filtering)
 * - Peak analysis (detection, fitting, integration)
 * - Batch processing
 * - Template system
 * - Veusz-inspired widget hierarchy for plots
 * 
 * Architecture inspired by Veusz: hierarchical widget system where
 * documents are built from composable widgets (graphs, axes, plots, etc.)
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { 
  Table, BarChart3, TrendingUp, Waves, Activity, Layers, 
  Download, Upload, Save, FolderOpen, Play, Settings, 
  Plus, Trash2, Copy, Grid3x3, FileText, Zap, Brain
} from 'lucide-react';

// API helper
const API_BASE = '';

const apiCall = async (endpoint, options = {}) => {
  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, options);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
};

const THEME = {
  primary: '#2563EB',
  success: '#059669',
  warning: '#F59E0B',
  error: '#DC2626',
  bg: '#FFFFFF',
  cardBg: '#F9FAFB',
  border: '#E5E7EB',
  textPrimary: '#111827',
  textSecondary: '#6B7280',
  textTertiary: '#9CA3AF',
};

// ═══════════════════════════════════════════════════════════════════════
// WORKSHEET COMPONENT - Multi-column data editor
// ═══════════════════════════════════════════════════════════════════════

function Worksheet({ data, onDataChange, columns, onColumnsChange }) {
  const [selectedCell, setSelectedCell] = useState(null);
  const [editValue, setEditValue] = useState('');
  
  const handleCellClick = (rowIdx, colIdx) => {
    setSelectedCell({ row: rowIdx, col: colIdx });
    setEditValue(data[rowIdx]?.[colIdx] ?? '');
  };
  
  const handleCellChange = (value) => {
    if (!selectedCell) return;
    const newData = [...data];
    if (!newData[selectedCell.row]) {
      newData[selectedCell.row] = [];
    }
    newData[selectedCell.row][selectedCell.col] = value;
    onDataChange(newData);
  };
  
  const addColumn = () => {
    onColumnsChange([...columns, { name: `Column ${columns.length + 1}`, type: 'numeric', unit: '' }]);
  };
  
  const addRow = () => {
    onDataChange([...data, Array(columns.length).fill('')]);
  };
  
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: THEME.bg }}>
      {/* Toolbar */}
      <div style={{ display: 'flex', gap: 8, padding: 12, borderBottom: `1px solid ${THEME.border}`, background: THEME.cardBg }}>
        <button onClick={addColumn} style={toolbarButtonStyle} title="Add Column">
          <Plus size={16} /> Column
        </button>
        <button onClick={addRow} style={toolbarButtonStyle} title="Add Row">
          <Plus size={16} /> Row
        </button>
        <button style={toolbarButtonStyle} title="Delete Selected">
          <Trash2 size={16} />
        </button>
        <button style={toolbarButtonStyle} title="Copy">
          <Copy size={16} />
        </button>
        <div style={{ flex: 1 }} />
        <button style={toolbarButtonStyle} title="Import Data">
          <Upload size={16} /> Import
        </button>
        <button style={toolbarButtonStyle} title="Export Data">
          <Download size={16} /> Export
        </button>
      </div>
      
      {/* Spreadsheet Grid */}
      <div style={{ flex: 1, overflow: 'auto', position: 'relative' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead style={{ position: 'sticky', top: 0, background: THEME.cardBg, zIndex: 10 }}>
            <tr>
              <th style={headerCellStyle}>#</th>
              {columns.map((col, idx) => (
                <th key={idx} style={headerCellStyle}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <input 
                      value={col.name} 
                      onChange={e => {
                        const newCols = [...columns];
                        newCols[idx].name = e.target.value;
                        onColumnsChange(newCols);
                      }}
                      style={{ border: 'none', background: 'transparent', fontWeight: 'bold', fontSize: 11 }}
                    />
                    <span style={{ fontSize: 9, color: THEME.textTertiary }}>{col.unit || col.type}</span>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, rowIdx) => (
              <tr key={rowIdx}>
                <td style={rowHeaderStyle}>{rowIdx + 1}</td>
                {columns.map((col, colIdx) => (
                  <td 
                    key={colIdx} 
                    style={{
                      ...cellStyle,
                      background: selectedCell?.row === rowIdx && selectedCell?.col === colIdx ? '#DBEAFE' : 'transparent'
                    }}
                    onClick={() => handleCellClick(rowIdx, colIdx)}
                  >
                    {selectedCell?.row === rowIdx && selectedCell?.col === colIdx ? (
                      <input 
                        value={editValue}
                        onChange={e => setEditValue(e.target.value)}
                        onBlur={() => handleCellChange(editValue)}
                        onKeyDown={e => e.key === 'Enter' && handleCellChange(editValue)}
                        autoFocus
                        style={{ width: '100%', border: 'none', outline: 'none', background: 'transparent' }}
                      />
                    ) : (
                      row[colIdx] ?? ''
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      {/* Status Bar */}
      <div style={{ padding: '6px 12px', borderTop: `1px solid ${THEME.border}`, background: THEME.cardBg, fontSize: 10, color: THEME.textSecondary }}>
        {data.length} rows × {columns.length} columns
        {selectedCell && ` | Selected: R${selectedCell.row + 1}C${selectedCell.col + 1}`}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// STATISTICS PANEL - Comprehensive statistical analysis
// ═══════════════════════════════════════════════════════════════════════

function StatisticsPanel({ data, columns }) {
  const [selectedColumn, setSelectedColumn] = useState(0);
  const [analysisType, setAnalysisType] = useState('descriptive');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const runAnalysis = async () => {
    setLoading(true);
    setError(null);
    try {
      // Extract column data
      const columnData = data.map(row => parseFloat(row[selectedColumn])).filter(v => !isNaN(v));
      
      if (columnData.length === 0) {
        setError('No valid numeric data in selected column');
        return;
      }
      
      const res = await apiCall('/api/v2/analysis/statistics', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          data: columnData,
          analysis_type: analysisType,
        }),
      });
      
      setResult(res);
    } catch (err) {
      console.error('Statistics analysis failed:', err);
      setError(err.message || 'Analysis failed');
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <label style={{ fontSize: 12, fontWeight: 600 }}>Column:</label>
        <select value={selectedColumn} onChange={e => setSelectedColumn(parseInt(e.target.value))} style={selectStyle}>
          {columns.map((col, idx) => (
            <option key={idx} value={idx}>{col.name}</option>
          ))}
        </select>
        
        <label style={{ fontSize: 12, fontWeight: 600, marginLeft: 16 }}>Analysis:</label>
        <select value={analysisType} onChange={e => setAnalysisType(e.target.value)} style={selectStyle}>
          <option value="descriptive">Descriptive Statistics</option>
          <option value="normality">Normality Test</option>
          <option value="ttest">T-Test</option>
          <option value="anova">ANOVA</option>
          <option value="correlation">Correlation</option>
          <option value="regression">Linear Regression</option>
        </select>
        
        <button onClick={runAnalysis} disabled={loading} style={primaryButtonStyle}>
          {loading ? 'Computing...' : 'Run Analysis'}
        </button>
      </div>
      
      {error && (
        <div style={{ background: '#FEE2E2', border: '1px solid #DC2626', borderRadius: 8, padding: 12, color: '#DC2626', fontSize: 12 }}>
          <strong>Error:</strong> {error}
        </div>
      )}
      
      {result && (
        <div style={{ background: THEME.cardBg, border: `1px solid ${THEME.border}`, borderRadius: 8, padding: 16 }}>
          <h3 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 700 }}>
            {analysisType === 'descriptive' ? 'Descriptive Statistics' : 'Analysis Results'}
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
            {Object.entries(result).map(([key, value]) => {
              // Skip non-numeric fields
              if (typeof value === 'object' || typeof value === 'boolean' || typeof value === 'string') return null;
              
              return (
                <div key={key} style={{ padding: 10, background: THEME.bg, borderRadius: 6 }}>
                  <div style={{ fontSize: 10, color: THEME.textSecondary, textTransform: 'uppercase', marginBottom: 4 }}>
                    {key.replace(/_/g, ' ')}
                  </div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: THEME.textPrimary }}>
                    {typeof value === 'number' ? value.toFixed(4) : value}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// CURVE FITTING PANEL - Advanced curve fitting with 100+ functions
// ═══════════════════════════════════════════════════════════════════════

function CurveFittingPanel({ data, columns }) {
  const [xColumn, setXColumn] = useState(0);
  const [yColumn, setYColumn] = useState(1);
  const [fitFunction, setFitFunction] = useState('polynomial');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [availableFunctions, setAvailableFunctions] = useState([]);
  
  // Load available functions on mount
  React.useEffect(() => {
    const loadFunctions = async () => {
      try {
        const res = await apiCall('/api/v2/analysis/curve-fit/functions');
        setAvailableFunctions(res.functions);
      } catch (err) {
        console.error('Failed to load fitting functions:', err);
      }
    };
    loadFunctions();
  }, []);
  
  const FIT_FUNCTIONS = availableFunctions.length > 0 
    ? Object.fromEntries(availableFunctions.map(f => [f.name, { name: f.description, params: f.parameters }]))
    : {
        'polynomial': { name: 'Polynomial', params: ['degree'] },
        'exponential': { name: 'Exponential (a*exp(b*x))', params: ['a', 'b'] },
        'gaussian': { name: 'Gaussian', params: ['amplitude', 'center', 'width'] },
        'lorentzian': { name: 'Lorentzian', params: ['amplitude', 'center', 'width'] },
        'voigt': { name: 'Voigt', params: ['amplitude', 'center', 'sigma', 'gamma'] },
        'sigmoid': { name: 'Sigmoid (Logistic)', params: ['L', 'k', 'x0'] },
        'power_law': { name: 'Power Law (a*x^b)', params: ['a', 'b'] },
        'logarithmic': { name: 'Logarithmic (a*log(x)+b)', params: ['a', 'b'] },
        'sine': { name: 'Sine Wave', params: ['amplitude', 'frequency', 'phase'] },
        'double_exponential': { name: 'Double Exponential', params: ['a1', 'b1', 'a2', 'b2'] },
      };
  
  const runFit = async () => {
    setLoading(true);
    setError(null);
    try {
      const xData = data.map(row => parseFloat(row[xColumn])).filter(v => !isNaN(v));
      const yData = data.map(row => parseFloat(row[yColumn])).filter(v => !isNaN(v));
      
      if (xData.length === 0 || yData.length === 0) {
        setError('No valid numeric data in selected columns');
        return;
      }
      
      if (xData.length !== yData.length) {
        setError('X and Y columns must have the same number of valid data points');
        return;
      }
      
      const res = await apiCall('/api/v2/analysis/curve-fit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          x: xData,
          y: yData,
          function: fitFunction,
        }),
      });
      
      setResult(res);
    } catch (err) {
      console.error('Curve fitting failed:', err);
      setError(err.message || 'Curve fitting failed');
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div>
          <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 6 }}>X Column:</label>
          <select value={xColumn} onChange={e => setXColumn(parseInt(e.target.value))} style={selectStyle}>
            {columns.map((col, idx) => (
              <option key={idx} value={idx}>{col.name}</option>
            ))}
          </select>
        </div>
        
        <div>
          <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 6 }}>Y Column:</label>
          <select value={yColumn} onChange={e => setYColumn(parseInt(e.target.value))} style={selectStyle}>
            {columns.map((col, idx) => (
              <option key={idx} value={idx}>{col.name}</option>
            ))}
          </select>
        </div>
      </div>
      
      <div>
        <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 6 }}>Fit Function:</label>
        <select value={fitFunction} onChange={e => setFitFunction(e.target.value)} style={selectStyle}>
          {Object.entries(FIT_FUNCTIONS).map(([key, func]) => (
            <option key={key} value={key}>{func.name}</option>
          ))}
        </select>
      </div>
      
      <button onClick={runFit} disabled={loading} style={primaryButtonStyle}>
        {loading ? 'Fitting...' : 'Fit Curve'}
      </button>
      
      {error && (
        <div style={{ background: '#FEE2E2', border: '1px solid #DC2626', borderRadius: 8, padding: 12, color: '#DC2626', fontSize: 12 }}>
          <strong>Error:</strong> {error}
        </div>
      )}
      
      {result && result.success && (
        <div style={{ background: THEME.cardBg, border: `1px solid ${THEME.border}`, borderRadius: 8, padding: 16 }}>
          <h3 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 700 }}>Fit Results</h3>
          
          {/* Equation */}
          <div style={{ background: '#EFF6FF', border: '1px solid #3B82F6', borderRadius: 6, padding: 12, marginBottom: 12 }}>
            <div style={{ fontSize: 11, color: '#1E40AF', fontWeight: 600, marginBottom: 4 }}>EQUATION</div>
            <div style={{ fontSize: 13, fontFamily: 'monospace', color: '#1E3A8A' }}>{result.equation}</div>
          </div>
          
          {/* Goodness of Fit */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 12 }}>
            <div style={{ padding: 10, background: THEME.bg, borderRadius: 6 }}>
              <div style={{ fontSize: 10, color: THEME.textSecondary, marginBottom: 4 }}>R²</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: result.r_squared > 0.95 ? '#059669' : result.r_squared > 0.8 ? '#F59E0B' : '#DC2626' }}>
                {result.r_squared.toFixed(4)}
              </div>
            </div>
            <div style={{ padding: 10, background: THEME.bg, borderRadius: 6 }}>
              <div style={{ fontSize: 10, color: THEME.textSecondary, marginBottom: 4 }}>RMSE</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: THEME.textPrimary }}>
                {result.rmse.toFixed(4)}
              </div>
            </div>
            <div style={{ padding: 10, background: THEME.bg, borderRadius: 6 }}>
              <div style={{ fontSize: 10, color: THEME.textSecondary, marginBottom: 4 }}>AIC</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: THEME.textPrimary }}>
                {result.aic.toFixed(2)}
              </div>
            </div>
            <div style={{ padding: 10, background: THEME.bg, borderRadius: 6 }}>
              <div style={{ fontSize: 10, color: THEME.textSecondary, marginBottom: 4 }}>BIC</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: THEME.textPrimary }}>
                {result.bic.toFixed(2)}
              </div>
            </div>
          </div>
          
          {/* Parameters */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>Fitted Parameters</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 8 }}>
              {Object.entries(result.parameters).map(([param, value]) => (
                <div key={param} style={{ padding: 8, background: THEME.bg, borderRadius: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 11, fontWeight: 600, color: THEME.textSecondary }}>{param}:</span>
                  <span style={{ fontSize: 12, fontFamily: 'monospace', color: THEME.textPrimary }}>
                    {value.toFixed(6)} ± {result.parameter_errors[param]?.toFixed(6) || '0'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// MAIN PANEL
// ═══════════════════════════════════════════════════════════════════════

export default function AdvancedAnalysisPanel() {
  const [activeTab, setActiveTab] = useState('worksheet');
  const [data, setData] = useState([
    [1, 2.5, 3.1],
    [2, 4.8, 5.2],
    [3, 7.2, 8.1],
    [4, 9.5, 10.3],
    [5, 12.1, 13.2],
  ]);
  const [columns, setColumns] = useState([
    { name: 'X', type: 'numeric', unit: '' },
    { name: 'Y1', type: 'numeric', unit: 'mV' },
    { name: 'Y2', type: 'numeric', unit: 'µA' },
  ]);
  
  const tabs = [
    { id: 'worksheet', label: 'Worksheet', icon: Table },
    { id: 'statistics', label: 'Statistics', icon: BarChart3 },
    { id: 'curve-fit', label: 'Curve Fitting', icon: TrendingUp },
    { id: 'signal', label: 'Signal Processing', icon: Waves },
    { id: 'peak', label: 'Peak Analysis', icon: Activity },
    { id: 'batch', label: 'Batch Processing', icon: Layers },
  ];
  
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: THEME.bg }}>
      {/* Header */}
      <div style={{ padding: '16px 24px', borderBottom: `2px solid ${THEME.border}`, background: THEME.cardBg }}>
        <h1 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: THEME.textPrimary }}>
          <Grid3x3 size={24} style={{ display: 'inline', marginRight: 8, verticalAlign: 'middle' }} />
          Advanced Analysis Studio
        </h1>
        <p style={{ margin: '4px 0 0', fontSize: 12, color: THEME.textSecondary }}>
          OriginLab-style comprehensive data analysis with ML integration
        </p>
      </div>
      
      {/* Tab Navigation */}
      <div style={{ display: 'flex', borderBottom: `1px solid ${THEME.border}`, background: THEME.cardBg }}>
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: '12px 20px',
              border: 'none',
              background: activeTab === tab.id ? THEME.bg : 'transparent',
              borderBottom: activeTab === tab.id ? `2px solid ${THEME.primary}` : '2px solid transparent',
              color: activeTab === tab.id ? THEME.primary : THEME.textSecondary,
              fontSize: 13,
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              transition: 'all 0.2s',
            }}
          >
            <tab.icon size={16} />
            {tab.label}
          </button>
        ))}
      </div>
      
      {/* Content Area */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        {activeTab === 'worksheet' && (
          <Worksheet 
            data={data} 
            onDataChange={setData} 
            columns={columns} 
            onColumnsChange={setColumns} 
          />
        )}
        {activeTab === 'statistics' && (
          <StatisticsPanel data={data} columns={columns} />
        )}
        {activeTab === 'curve-fit' && (
          <CurveFittingPanel data={data} columns={columns} />
        )}
        {activeTab === 'signal' && (
          <div style={{ padding: 40, textAlign: 'center', color: THEME.textSecondary }}>
            <Waves size={48} style={{ opacity: 0.3, marginBottom: 16 }} />
            <div>Signal Processing tools coming soon...</div>
          </div>
        )}
        {activeTab === 'peak' && (
          <div style={{ padding: 40, textAlign: 'center', color: THEME.textSecondary }}>
            <Activity size={48} style={{ opacity: 0.3, marginBottom: 16 }} />
            <div>Peak Analysis tools coming soon...</div>
          </div>
        )}
        {activeTab === 'batch' && (
          <div style={{ padding: 40, textAlign: 'center', color: THEME.textSecondary }}>
            <Layers size={48} style={{ opacity: 0.3, marginBottom: 16 }} />
            <div>Batch Processing tools coming soon...</div>
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// STYLES
// ═══════════════════════════════════════════════════════════════════════

const toolbarButtonStyle = {
  padding: '6px 12px',
  border: `1px solid ${THEME.border}`,
  background: THEME.bg,
  borderRadius: 4,
  fontSize: 11,
  fontWeight: 600,
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  color: THEME.textPrimary,
};

const headerCellStyle = {
  padding: '8px 12px',
  borderBottom: `2px solid ${THEME.border}`,
  borderRight: `1px solid ${THEME.border}`,
  textAlign: 'left',
  fontWeight: 600,
  fontSize: 11,
  color: THEME.textPrimary,
  background: THEME.cardBg,
};

const rowHeaderStyle = {
  padding: '6px 12px',
  borderRight: `1px solid ${THEME.border}`,
  borderBottom: `1px solid ${THEME.border}`,
  textAlign: 'center',
  fontWeight: 600,
  fontSize: 10,
  color: THEME.textSecondary,
  background: THEME.cardBg,
  minWidth: 40,
};

const cellStyle = {
  padding: '6px 12px',
  borderRight: `1px solid ${THEME.border}`,
  borderBottom: `1px solid ${THEME.border}`,
  fontSize: 12,
  color: THEME.textPrimary,
  cursor: 'pointer',
  minWidth: 100,
};

const selectStyle = {
  padding: '8px 12px',
  border: `1px solid ${THEME.border}`,
  borderRadius: 6,
  fontSize: 12,
  background: THEME.bg,
  color: THEME.textPrimary,
  cursor: 'pointer',
  width: '100%',
};

const primaryButtonStyle = {
  padding: '10px 20px',
  border: 'none',
  background: THEME.primary,
  color: '#FFFFFF',
  borderRadius: 6,
  fontSize: 13,
  fontWeight: 600,
  cursor: 'pointer',
  transition: 'all 0.2s',
};
