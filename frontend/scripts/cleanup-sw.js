#!/usr/bin/env node

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Function to clean up service worker files
function cleanupServiceWorker() {
  const devDistPath = path.join(__dirname, '..', 'dev-dist');
  const distPath = path.join(__dirname, '..', 'dist');
  
  console.log('🧹 Limpiando archivos de Service Worker...');
  
  // Files to remove
  const filesToRemove = [
    'sw.js',
    'sw.js.map',
    'workbox-*.js',
    'workbox-*.js.map',
    'registerSW.js',
    'suppress-warnings.js'
  ];
  
  // Clean dev-dist directory
  if (fs.existsSync(devDistPath)) {
    filesToRemove.forEach(pattern => {
      const files = fs.readdirSync(devDistPath).filter(file => {
        if (pattern.includes('*')) {
          const regex = new RegExp(pattern.replace(/\*/g, '.*'));
          return regex.test(file);
        }
        return file === pattern;
      });
      
      files.forEach(file => {
        const filePath = path.join(devDistPath, file);
        try {
          fs.unlinkSync(filePath);
          console.log(`✅ Eliminado: ${file}`);
        } catch (error) {
          console.log(`⚠️  No se pudo eliminar: ${file} - ${error.message}`);
        }
      });
    });
  }
  
  // Clean dist directory
  if (fs.existsSync(distPath)) {
    filesToRemove.forEach(pattern => {
      const files = fs.readdirSync(distPath).filter(file => {
        if (pattern.includes('*')) {
          const regex = new RegExp(pattern.replace(/\*/g, '.*'));
          return regex.test(file);
        }
        return file === pattern;
      });
      
      files.forEach(file => {
        const filePath = path.join(distPath, file);
        try {
          fs.unlinkSync(filePath);
          console.log(`✅ Eliminado: ${file}`);
        } catch (error) {
          console.log(`⚠️  No se pudo eliminar: ${file} - ${error.message}`);
        }
      });
    });
  }
  
  console.log('✨ Limpieza completada. Reinicia el servidor de desarrollo para regenerar los archivos.');
}

// Run cleanup
cleanupServiceWorker();
