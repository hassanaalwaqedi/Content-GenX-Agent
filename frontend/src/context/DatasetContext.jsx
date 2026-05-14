import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';

const DatasetContext = createContext(null);

export function DatasetProvider({ children }) {
  const [activeDataset, setActiveDataset] = useState(null);
  const [datasetStats, setDatasetStats] = useState(null);
  const [datasets, setDatasets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [allData, setAllDataMode] = useState(false);

  const refreshDatasets = useCallback(async () => {
    try {
      const [activeRes, listRes] = await Promise.all([
        api.getActiveDataset(),
        api.getDatasets(),
      ]);
      setActiveDataset(activeRes.active);
      setDatasetStats(activeRes.stats);
      setDatasets(listRes.datasets || []);
    } catch (err) {
      console.error('Failed to load datasets:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const switchDataset = useCallback(async (runId) => {
    try {
      setLoading(true);
      setAllDataMode(false);
      const res = await api.activateDataset(runId);
      setActiveDataset(res.active);
      setDatasetStats(res.stats);
      // Refresh list to update active indicator
      const listRes = await api.getDatasets();
      setDatasets(listRes.datasets || []);
    } catch (err) {
      console.error('Failed to switch dataset:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const setAllData = useCallback(() => {
    setAllDataMode(true);
    setDatasetStats(null);
  }, []);

  useEffect(() => {
    refreshDatasets();
  }, [refreshDatasets]);

  const value = {
    activeDataset: allData ? null : activeDataset,
    datasetStats,
    datasets,
    loading,
    datasetId: allData ? null : (activeDataset?.id ?? null),
    switchDataset,
    refreshDatasets,
    setAllData,
    allData,
  };

  return (
    <DatasetContext.Provider value={value}>
      {children}
    </DatasetContext.Provider>
  );
}

export function useDataset() {
  const ctx = useContext(DatasetContext);
  if (!ctx) {
    throw new Error('useDataset must be used within a DatasetProvider');
  }
  return ctx;
}

export default DatasetContext;
