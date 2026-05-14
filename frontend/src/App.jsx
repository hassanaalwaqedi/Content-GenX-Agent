import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { DatasetProvider } from './context/DatasetContext';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import TopVideos from './pages/TopVideos';
import Trending from './pages/Trending';
import VideoDetail from './pages/VideoDetail';
import Creators from './pages/Creators';
import Pipeline from './pages/Pipeline';

export default function App() {
  return (
    <BrowserRouter>
      <DatasetProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/videos" element={<TopVideos />} />
            <Route path="/trending" element={<Trending />} />
            <Route path="/video/:id" element={<VideoDetail />} />
            <Route path="/creators" element={<Creators />} />
            <Route path="/pipeline" element={<Pipeline />} />
          </Route>
        </Routes>
      </DatasetProvider>
    </BrowserRouter>
  );
}
