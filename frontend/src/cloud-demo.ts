import JSZip from 'jszip';

export const CLOUD_DEMO = (import.meta as unknown as {env:Record<string,string>}).env.VITE_CLOUD_DEMO === '1';
type Obj = Record<string, any>;
const KEY = 'notepilot-cloud-demo-v1';
function load():Obj[]{try{return JSON.parse(localStorage.getItem(KEY)||'[]')}catch{return []}}
function persist(p:Obj){const all=load().filter(x=>x.id!==p.id);localStorage.setItem(KEY,JSON.stringify([p,...all].slice(0,30)));return p}
function update(p:Obj){p.revision++;p.updated_at=new Date().toISOString();return persist(p)}
const patterns=['可收藏的入门行动清单','常见误区与替代做法','一个小任务的完整过程'];

export async function demoApi(path:string,data?:Obj):Promise<any>{
  const all=load();
  if(path==='/projects'&&!data)return all.map(p=>({id:p.id,intent:p.brief.intent,status:p.status,revision:p.revision}));
  if(path==='/projects'&&data){
    if(data.mode==='live')throw Error('云端演示未连接模型和小红书服务，请选择离线演示。');
    const samples=[...patterns.map((title,i)=>({id:'demo-'+i,title:'演示结构：'+title,likes:null,saves:null,comments:null,url:null,questions:['应该从哪里开始？']})),...(data.samples||[])];
    const p={id:crypto.randomUUID(),revision:1,status:'awaiting_angle',brief:data,approval:null,issues:[],trend:{samples,music:data.music||[],coverage:'demo',visual_analysis:[],warnings:['云端演示在浏览器内运行，作品仅保存在当前浏览器。','内置案例是虚构结构样本，不是实时热门。','未连接真实模型、封面视觉分析或 BGM 榜单。']},plan:{angles:patterns.map((title,i)=>({id:String(i),title,reason:'按目标组织清晰、有行动价值的内容。',contribution:'补充实践步骤与结果检查清单。',sample_ids:['demo-'+i]}))}};
    return persist(p);
  }
  const [, ,id,operation]=path.split('/');
  const p=all.find(x=>x.id===id);
  if(!p)throw Error('作品不存在');
  if(!operation)return p;
  if(data?.revision!==undefined&&data.revision!==p.revision)throw Error('版本已变化，请刷新作品');
  if(operation==='image')throw Error('云端 UI 演示未接入图片模型；请运行 GitHub 完整版配置图片接口。');
  if(operation==='select'||operation==='retry'){
    p.selected=p.plan.angles.find((a:Obj)=>a.id===(data?.angle_id||p.selected?.id||'0'));
    const parts=[['cover',p.selected.title,[p.brief.intent,'一份可以照着做的行动清单']],['steps','01 / 先把目标缩小',['写下要完成的一件具体事情。','明确读者与预期结果。']],['compare','02 / 收集可信参考',['查阅原始资料，再参考同类内容结构。','热门提供灵感，事实仍需核对。']],['steps','03 / 一次只做一步',['拆成输入、行动与输出。','完成最小结果，再逐步补充。']],['steps','04 / 用结果验收',['实际执行并记录修改。','只写真实做过的事。']],['summary','保存这份行动清单',['目标明确 · 来源可查 · 步骤可执行','结果可验证 · 配图一致 · 音乐适配']]];
    p.draft={titles:[p.selected.title],caption:'【云端演示文案，发布前请补充真实内容】\n\n'+p.brief.intent+'\n\n明确目标、收集参考、分步执行、验证结果。\n\nAI 辅助创作。',tags:['学习方法','行动清单'],palette:'mint',music_id:null,music_reason:'暂无可核验音乐。发布时确认平台曲库；可在新建作品时导入音乐候选。',slides:parts.map(([kind,title,body],i)=>({id:'s'+(i+1),kind,title,body,sample_ids:['demo-0'],image_prompt:'极简编辑插画，无文字'}))};
    p.status='review';p.approval=null;p.issues=[];return update(p);
  }
  if(operation==='draft'){
    p.draft=data!.draft;p.approval=null;p.status='review';p.issues=[];
    const samples=new Set(p.trend.samples.map((x:Obj)=>x.id));
    if(p.draft.slides.length!==6)p.issues.push('演示版使用 6 页，请保持页面数量');
    for(const s of p.draft.slides){if(s.title.length>32||s.body.some((b:string)=>b.length>100)||s.body.join('').length>320)p.issues.push(s.id+' 文字过密，请缩短');if(s.sample_ids.some((id:string)=>!samples.has(id)))p.issues.push('参考引用不存在');}
    if(p.draft.music_id&&!p.trend.music.some((m:Obj)=>m.id===p.draft.music_id))p.issues.push('音乐候选不存在');
    return update(p);
  }
  if(operation==='approve'){if(p.issues.length)throw Error('请先修复问题');p.status='approved';p.approval={revision:p.revision+1};return update(p)}
  if(operation==='cancel')return p;
  throw Error('云端演示不支持此操作');
}

function wrap(ctx:CanvasRenderingContext2D,text:string,width:number):string[]{const rows:string[]=[];let row='';for(const char of text){if(ctx.measureText(row+char).width>width&&row){rows.push(row);row=char}else row+=char}if(row)rows.push(row);return rows}
async function pagePng(slide:Obj,palette:string,index:number):Promise<Blob>{
  await document.fonts.load('400 76px "Noto Sans SC"',slide.title+slide.body.join(''));
  const palettes:Obj={mint:['#f4f6ef','#1b3430','#b8d5c4'],ink:['#ececf0','#222632','#c5c5ef'],peach:['#fff3eb','#51372f','#f4c6af']};
  const [bg,fg,accent]=palettes[palette]||palettes.mint;
  const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1440;const c=canvas.getContext('2d')!;
  c.fillStyle=bg;c.fillRect(0,0,1080,1440);c.fillStyle=fg;c.font='25px "Noto Sans SC",sans-serif';c.fillText('NOTEPILOT / FIELD NOTES',86,116);c.fillText(String(index).padStart(2,'0')+'—06',890,116);c.fillRect(86,149,908,2);
  c.fillStyle=accent;c.beginPath();c.roundRect(86,200,280,64,32);c.fill();c.fillStyle=fg;c.font='25px "Noto Sans SC",sans-serif';c.fillText('入门行动指南',110,241);
  c.font='76px "Noto Sans SC",sans-serif';let y=375;for(const line of wrap(c,slide.title,908)){c.fillText(line,86,y);y+=102}
  if(slide.kind==='cover'){c.fillStyle=accent;c.beginPath();c.roundRect(86,y+15,908,290,[150,150,30,30]);c.fill();c.fillStyle=fg;c.font='160px sans-serif';c.fillText('✳',210,y+217);c.font='bold 56px sans-serif';c.fillText('MAKE IT',615,y+140);c.fillText('HAPPEN.',615,y+215);y+=350}
  c.font='32px "Noto Sans SC",sans-serif';
  for(const [i,text] of (slide.body as string[]).entries()){
    const lines=wrap(c,text,790),height=lines.length*52+44;
    if(y+height>1290)throw Error('第 '+index+' 页文字溢出，请缩短并重新审核');
    c.fillStyle='#ffffff99';c.beginPath();c.roundRect(86,y,908,height,20);c.fill();c.fillStyle=fg;c.font='25px sans-serif';c.fillText(String(i+1).padStart(2,'0'),110,y+44);c.font='32px "Noto Sans SC",sans-serif';for(const [j,line] of lines.entries())c.fillText(line,175,y+46+j*52);y+=height+25;
  }
  c.fillStyle=fg;c.fillRect(86,1338,908,2);c.font='23px "Noto Sans SC",sans-serif';c.fillText('AI 辅助创作 · 云端演示',86,1383);c.fillText('保存 · 实践 · 复盘',770,1383);
  return new Promise((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(Error('图片导出失败')),'image/png'));
}

export async function demoExport(project:Obj){
  if(project.approval?.revision!==project.revision)throw Error('请先审核当前版本');
  const zip=new JSZip();for(const [i,slide] of project.draft.slides.entries())zip.file(String(i+1).padStart(2,'0')+'.png',await pagePng(slide,project.draft.palette,i+1));
  zip.file('caption.md',project.draft.titles[0]+'\n\n'+project.draft.caption);
  zip.file('sources.json',JSON.stringify(project.trend,null,2));zip.file('project.json',JSON.stringify(project,null,2));
  zip.file('music.md',project.draft.music_reason+'\n'+JSON.stringify(project.trend.music.find((m:Obj)=>m.id===project.draft.music_id)||null,null,2)+'\n本包不包含音频，发布时核验曲库。');
  const url=URL.createObjectURL(await zip.generateAsync({type:'blob'}));const a=document.createElement('a');a.href=url;a.download='notepilot-demo-'+project.id.slice(0,8)+'.zip';a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);
}
