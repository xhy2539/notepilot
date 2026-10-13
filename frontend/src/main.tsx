import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import '@fontsource/noto-sans-sc';
import '@fontsource/noto-sans-sc/500.css';
import '@fontsource/noto-sans-sc/600.css';
import './style.css';
createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>);
