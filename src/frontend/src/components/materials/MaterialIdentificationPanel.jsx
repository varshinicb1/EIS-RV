/**
 * Material Identification Panel
 * ==============================
 * Predictive material identification from lab data using inverse problem solving.
 * 
 * Features:
 * - Upload EIS/CV/Raman data from CHI608E or other instruments
 * - Automatic material identification with confidence scores
 * - Multi-modal fusion for higher accuracy
 * - Synthesis route suggestions with cost estimates
 * - Replace physical lab synthesis with predictive simulation
 * 
 * Author: VidyuthLabs
 * Date: May 9, 2026
 */

import React, { useState, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Alert,
  CircularProgress,
  Chip,
  Divider,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Grid,
  LinearProgress,
  Tooltip,
  IconButton,
} from '@mui/material';
import {
  Upload as UploadIcon,
  Science as ScienceIcon,
  ExpandMore as ExpandMoreIcon,
  CheckCircle as CheckCircleIcon,
  Info as InfoIcon,
  TrendingUp as TrendingUpIcon,
  AttachMoney as MoneyIcon,
} from '@mui/icons-material';
import { useDropzone } from 'react-dropzone';
import Plot from 'react-plotly.js';

const API_BASE = '';

// API helper
const apiCall = async (endpoint, options = {}) => {
  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, options);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
};

export default function MaterialIdentificationPanel() {
  const [mode, setMode] = useState('single'); // 'single' or 'multimodal'
  const [modality, setModality] = useState('eis'); // 'eis', 'cv', 'raman'
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  
  // Data states
  const [eisData, setEisData] = useState(null);
  const [cvData, setCvData] = useState(null);
  const [ramanData, setRamanData] = useState(null);

  // File upload handler
  const onDrop = useCallback(async (acceptedFiles) => {
    if (acceptedFiles.length === 0) return;
    
    const file = acceptedFiles[0];
    setError(null);
    setLoading(true);
    
    try {
      // Use backend upload endpoint instead of parsing manually
      const formData = new FormData();
      formData.append('file', file);
      
      // Determine which upload endpoint to use based on modality
      let uploadEndpoint = '';
      if (modality === 'eis') {
        uploadEndpoint = '/api/v2/upload/eis';
      } else if (modality === 'cv') {
        uploadEndpoint = '/api/v2/upload/cv';
      } else if (modality === 'raman') {
        uploadEndpoint = '/api/v2/upload/raman';
      } else {
        throw new Error('Please select a modality first');
      }
      
      // Upload file to backend
      const response = await fetch(`${API_BASE}${uploadEndpoint}`, {
        method: 'POST',
        body: formData,
      });
      
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(error.detail || `HTTP ${response.status}`);
      }
      
      const data = await response.json();
      
      // Store parsed data based on modality
      if (modality === 'eis') {
        setEisData({
          frequency_Hz: data.frequencies,
          Z_real_ohm: data.Z_real,
          Z_imag_ohm: data.Z_imag,
        });
      } else if (modality === 'cv') {
        setCvData({
          potential_V: data.potential || data.voltage,
          current_A: data.current,
          scan_rate_V_s: data.scan_rate || 0.1,
        });
      } else if (modality === 'raman') {
        setRamanData({
          wavenumber_cm: data.wavenumber,
          intensity: data.intensity,
        });
      }
      
      setError(null);
      
    } catch (err) {
      setError(`Failed to upload file: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, [modality]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/plain': ['.txt', '.csv', '.dat'],
    },
    multiple: false,
  });

  // Run identification
  const runIdentification = async () => {
    setError(null);
    setLoading(true);
    setResult(null);
    
    try {
      let response;
      
      if (mode === 'multimodal') {
        // Multi-modal fusion - not yet implemented
        throw new Error('Multi-modal fusion is not yet implemented. Please use single modality mode.');
      } else {
        // Single modality
        if (modality === 'eis' && eisData) {
          response = await apiCall(`/api/v2/material-id/identify/eis`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              frequencies: eisData.frequency_Hz,
              Z_real: eisData.Z_real_ohm,
              Z_imag: eisData.Z_imag_ohm,
              top_k: 5,
            }),
          });
        } else if (modality === 'cv' && cvData) {
          response = await apiCall(`/api/v2/material-id/identify/cv`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              potential: cvData.potential_V,
              current: cvData.current_A,
              top_k: 5,
            }),
          });
        } else if (modality === 'raman' && ramanData) {
          response = await apiCall(`/api/v2/material-id/identify/raman`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              wavenumber: ramanData.wavenumber_cm,
              intensity: ramanData.intensity,
              top_k: 5,
            }),
          });
        } else {
          throw new Error('No data available for selected modality');
        }
      }
      
      // Transform response to match expected format
      const transformedResult = {
        confidence: response.confidence || 0.5,
        method: response.method || 'ml_model',
        compute_time_ms: response.compute_time_ms || 0,
        material_candidates: response.candidates || [],
        inferred_properties: response.inferred_properties || {},
        synthesis_suggestions: response.synthesis_suggestions || [],
      };
      
      setResult(transformedResult);
      
    } catch (err) {
      setError(err.message || 'Identification failed');
    } finally {
      setLoading(false);
    }
  };

  // Render confidence bar
  const ConfidenceBar = ({ confidence }) => {
    const percentage = confidence * 100;
    const color = percentage > 70 ? 'success' : percentage > 40 ? 'warning' : 'error';
    
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Box sx={{ flexGrow: 1 }}>
          <LinearProgress
            variant="determinate"
            value={percentage}
            color={color}
            sx={{ height: 8, borderRadius: 1 }}
          />
        </Box>
        <Typography variant="body2" sx={{ minWidth: 50 }}>
          {percentage.toFixed(1)}%
        </Typography>
      </Box>
    );
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <ScienceIcon fontSize="large" />
        Predictive Material Identification
      </Typography>
      
      <Typography variant="body2" color="text.secondary" paragraph>
        Upload lab data (EIS/CV/Raman) to automatically identify materials and get synthesis suggestions.
        Replace physical lab synthesis with AI-powered prediction.
      </Typography>

      <Grid container spacing={3}>
        {/* Left Panel: Data Upload */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                1. Upload Lab Data
              </Typography>
              
              <FormControl fullWidth sx={{ mb: 2 }}>
                <InputLabel>Mode</InputLabel>
                <Select
                  value={mode}
                  onChange={(e) => setMode(e.target.value)}
                  label="Mode"
                >
                  <MenuItem value="single">Single Modality</MenuItem>
                  <MenuItem value="multimodal">Multi-Modal Fusion</MenuItem>
                </Select>
              </FormControl>

              {mode === 'single' && (
                <FormControl fullWidth sx={{ mb: 2 }}>
                  <InputLabel>Modality</InputLabel>
                  <Select
                    value={modality}
                    onChange={(e) => setModality(e.target.value)}
                    label="Modality"
                  >
                    <MenuItem value="eis">EIS (Impedance)</MenuItem>
                    <MenuItem value="cv">CV (Cyclic Voltammetry)</MenuItem>
                    <MenuItem value="raman">Raman Spectroscopy</MenuItem>
                  </Select>
                </FormControl>
              )}

              <Paper
                {...getRootProps()}
                sx={{
                  p: 3,
                  border: '2px dashed',
                  borderColor: isDragActive ? 'primary.main' : 'grey.300',
                  bgcolor: isDragActive ? 'action.hover' : 'background.paper',
                  cursor: 'pointer',
                  textAlign: 'center',
                  transition: 'all 0.2s',
                  '&:hover': {
                    borderColor: 'primary.main',
                    bgcolor: 'action.hover',
                  },
                }}
              >
                <input {...getInputProps()} />
                <UploadIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 1 }} />
                <Typography variant="body2" color="text.secondary">
                  {isDragActive
                    ? 'Drop the file here'
                    : 'Drag & drop a data file, or click to browse'}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Supports: .txt, .csv, .dat
                </Typography>
              </Paper>

              {/* Data status */}
              <Box sx={{ mt: 2 }}>
                {eisData && (
                  <Chip
                    icon={<CheckCircleIcon />}
                    label={`EIS: ${eisData.frequency_Hz.length} points`}
                    color="success"
                    size="small"
                    sx={{ mr: 1, mb: 1 }}
                  />
                )}
                {cvData && (
                  <Chip
                    icon={<CheckCircleIcon />}
                    label={`CV: ${cvData.potential_V.length} points`}
                    color="success"
                    size="small"
                    sx={{ mr: 1, mb: 1 }}
                  />
                )}
                {ramanData && (
                  <Chip
                    icon={<CheckCircleIcon />}
                    label={`Raman: ${ramanData.wavenumber_cm.length} points`}
                    color="success"
                    size="small"
                    sx={{ mr: 1, mb: 1 }}
                  />
                )}
              </Box>

              <Button
                variant="contained"
                fullWidth
                onClick={runIdentification}
                disabled={loading || (!eisData && !cvData && !ramanData)}
                startIcon={loading ? <CircularProgress size={20} /> : <TrendingUpIcon />}
                sx={{ mt: 2 }}
              >
                {loading ? 'Analyzing...' : 'Identify Material'}
              </Button>

              {error && (
                <Alert severity="error" sx={{ mt: 2 }}>
                  {error}
                </Alert>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Right Panel: Results */}
        <Grid item xs={12} md={8}>
          {result ? (
            <Box>
              {/* Material Candidates */}
              <Card sx={{ mb: 2 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    2. Material Candidates
                  </Typography>
                  
                  <Typography variant="body2" color="text.secondary" paragraph>
                    Confidence: {(result.confidence * 100).toFixed(1)}% | 
                    Method: {result.method} | 
                    Compute time: {result.compute_time_ms}ms
                  </Typography>

                  {result.material_candidates && result.material_candidates.length > 0 ? (
                    result.material_candidates.slice(0, 5).map((candidate, idx) => (
                      <Accordion key={idx} defaultExpanded={idx === 0}>
                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
                            <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>
                              #{idx + 1}: {candidate.material_name || candidate.name}
                            </Typography>
                            <Chip
                              label={candidate.formula}
                              size="small"
                              color="primary"
                              variant="outlined"
                            />
                            <Box sx={{ flexGrow: 1 }} />
                            <Typography variant="body2" color="text.secondary">
                              {(candidate.confidence * 100).toFixed(1)}%
                            </Typography>
                          </Box>
                        </AccordionSummary>
                        <AccordionDetails>
                          <Box>
                            <ConfidenceBar confidence={candidate.confidence} />
                            
                            <Typography variant="body2" sx={{ mt: 2, mb: 1 }}>
                              <strong>Category:</strong> {candidate.category || 'Unknown'}
                            </Typography>
                            
                            {candidate.modality_used && (
                              <Typography variant="body2" sx={{ mb: 1 }}>
                                <strong>Modality:</strong> {candidate.modality_used}
                              </Typography>
                            )}
                            
                            {candidate.suggested_applications && candidate.suggested_applications.length > 0 && (
                              <Typography variant="body2" sx={{ mb: 1 }}>
                                <strong>Applications:</strong>{' '}
                                {candidate.suggested_applications.join(', ')}
                              </Typography>
                            )}
                            
                            {candidate.rationale && (
                              <Typography variant="body2" sx={{ mb: 1 }}>
                                <strong>Rationale:</strong> {candidate.rationale}
                              </Typography>
                            )}
                            
                            {candidate.matching_features && Object.keys(candidate.matching_features).length > 0 && (
                              <Box sx={{ mt: 2 }}>
                                <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 1 }}>
                                  Matching Features:
                                </Typography>
                                {Object.entries(candidate.matching_features).map(([key, value]) => (
                                  <Chip
                                    key={key}
                                    label={`${key}: ${value}`}
                                    size="small"
                                    sx={{ mr: 0.5, mb: 0.5 }}
                                  />
                                ))}
                              </Box>
                            )}
                          </Box>
                        </AccordionDetails>
                      </Accordion>
                    ))
                  ) : (
                    <Alert severity="info">
                      No material candidates found. The ML model may need training. Try loading the materials database first.
                    </Alert>
                  )}
                </CardContent>
              </Card>

              {/* Inferred Properties */}
              <Card sx={{ mb: 2 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    3. Inferred Properties
                  </Typography>
                  
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell><strong>Property</strong></TableCell>
                          <TableCell align="right"><strong>Value</strong></TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {Object.entries(result.inferred_properties).map(([key, value]) => (
                          <TableRow key={key}>
                            <TableCell>{key}</TableCell>
                            <TableCell align="right">
                              {typeof value === 'number' ? value.toExponential(3) : String(value)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>

              {/* Synthesis Suggestions */}
              {result.synthesis_suggestions && result.synthesis_suggestions.length > 0 && (
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <MoneyIcon />
                      4. Synthesis Suggestions
                    </Typography>
                    
                    <Typography variant="body2" color="text.secondary" paragraph>
                      Recommended synthesis routes based on identified materials:
                    </Typography>

                    <TableContainer>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell><strong>Material</strong></TableCell>
                            <TableCell><strong>Method</strong></TableCell>
                            <TableCell align="right"><strong>Cost ($/g)</strong></TableCell>
                            <TableCell><strong>Electrolytes</strong></TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {result.synthesis_suggestions.map((sug, idx) => (
                            <TableRow key={idx}>
                              <TableCell>
                                {sug.material}
                                <br />
                                <Typography variant="caption" color="text.secondary">
                                  {sug.formula}
                                </Typography>
                              </TableCell>
                              <TableCell>{sug.method}</TableCell>
                              <TableCell align="right">
                                ${sug.estimated_cost_per_gram?.toFixed(2) || 'N/A'}
                              </TableCell>
                              <TableCell>
                                {sug.typical_electrolytes?.join(', ') || 'N/A'}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  </CardContent>
                </Card>
              )}
            </Box>
          ) : (
            <Card>
              <CardContent>
                <Box sx={{ textAlign: 'center', py: 8 }}>
                  <ScienceIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
                  <Typography variant="h6" color="text.secondary">
                    Upload data and click "Identify Material" to begin
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    The AI will analyze your electrochemical data and predict material composition
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          )}
        </Grid>
      </Grid>
    </Box>
  );
}
