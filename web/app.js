const $ = id => document.getElementById(id);
let selected = [], encoded = [], busy = false;
const supported = /\.(dds|png|tga|jpe?g|webp)$/i;
function controls() { $('convert').disabled = busy || !encoded.length; $('folder').disabled = $('files').disabled = $('clear').disabled = busy; }
function status(text) { $('status').textContent = text; }
function read(file) { return new Promise((resolve, reject) => { const r = new FileReader(); r.onload = () => resolve({name:file.webkitRelativePath || file.name, data:r.result.split(',')[1]}); r.onerror = () => reject(new Error(`Cannot read ${file.name}`)); r.readAsDataURL(file); }); }
async function api(path, body) { const r = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}); if(!r.ok) { let e; try { e = await r.json(); } catch { throw new Error('The local server returned an error.'); } throw new Error(e.error || 'Request failed'); } return r; }
async function load(files) {
 if(busy) return;
 selected = [...files].filter(f => supported.test(f.name)); encoded = []; $('results').replaceChildren();
 const total = selected.reduce((n,f) => n+f.size,0);
 $('count').textContent = `${selected.length} FILES · ${(total/1048576).toFixed(1)} MB`;
 if(!selected.length) { status('No supported images found.'); controls(); return; }
 if(selected.length>200 || total>120*1048576) { status('Batch too large. Select up to 200 images totaling under 120 MB.'); controls(); return; }
 busy = true; controls(); status('Reading files and inspecting texture data…');
 try {
  encoded = await Promise.all(selected.map(read));
  const rows = await (await api('/api/inspect',{files:encoded})).json();
  let valid = 0;
  for(const row of rows) {
   const el = document.createElement('div'); el.className = 'texture';
   if(row.preview) { const img = document.createElement('img'); img.src = `data:image/png;base64,${row.preview}`; img.alt = ''; el.append(img); }
   const detail = document.createElement('div'); detail.className = 'detail';
   const name = document.createElement('strong'); name.textContent = row.name; detail.append(name);
   const meta = document.createElement('p'); meta.textContent = row.ok ? `${row.width} × ${row.height} · ${row.format} · ${row.mips} mip(s) · ${row.alpha ? 'transparency' : 'opaque'}` : row.error; if(!row.ok) meta.className='error'; detail.append(meta);
   if(row.ok) valid++;
   for(const warning of row.warnings || []) { const p = document.createElement('p'); p.className = 'warn'; p.textContent = warning; detail.append(p); }
   el.append(detail); $('results').append(el);
  }
  status(`${valid} of ${rows.length} images opened. Notes show settings to compare with a working render. They do not mean the file is broken.`);
 } catch(e) { encoded = []; status(e.message); } finally { busy=false; controls(); }
}
$('folder').onclick = () => $('folderInput').click(); $('files').onclick = () => $('fileInput').click();
for(const id of ['folderInput','fileInput']) $(id).onchange = e => load(e.target.files);
$('clear').onclick = () => { selected=[]; encoded=[]; $('results').replaceChildren(); $('count').textContent='NO FILES SELECTED'; $('folderInput').value=$('fileInput').value=''; status('Select a folder or files to get started.'); controls(); };
$('profile').onchange = () => { const odb = $('profile').value==='odb'; $('size').disabled=$('mips').disabled=odb; if(odb) { $('size').value='1024'; $('mips').checked=false; } };
for(const event of ['dragover','dragleave','drop']) $('drop').addEventListener(event,e=>{e.preventDefault(); $('drop').classList.toggle('drag',event==='dragover'); if(event==='drop') load(e.dataTransfer.files);});
$('convert').onclick = async () => {
 busy=true; controls(); $('convert').textContent='Converting…'; status('Processing your batch. Large images may take a moment.');
 try { const r=await api('/api/convert',{files:encoded,size:Number($('size').value),mipmaps:$('mips').checked}); const url=URL.createObjectURL(await r.blob()); const a=document.createElement('a'); a.href=url; a.download='render-workshop-output.zip'; a.click(); setTimeout(()=>URL.revokeObjectURL(url),60000); status('Export downloaded. Read conversion-report.json for successes and failures. Test an output in game before replacing your installed renders.'); }
 catch(e) { status(e.message); } finally { busy=false; $('convert').textContent='Save converted renders'; controls(); }
};
