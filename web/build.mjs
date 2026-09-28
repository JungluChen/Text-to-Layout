import {mkdir,copyFile,cp} from 'node:fs/promises';
import {build} from 'esbuild';
await mkdir('dist',{recursive:true});
for(const file of ['index.html','app.html','app.js','style.css']) await copyFile(file,`dist/${file}`);
await cp('assets','dist/assets',{recursive:true});
await build({entryPoints:['stack.js'],outfile:'dist/stack.bundle.js',bundle:true,format:'esm',minify:true,legalComments:'eof'});
await copyFile('node_modules/three/LICENSE','dist/THREE-LICENSE.txt');
