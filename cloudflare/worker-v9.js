import base from './worker-v6.js';

const ORCH_OLD='/functions/v1/socialscheduler-orchestrator-api';
const ORCH_NEW='/functions/v1/socialscheduler-orchestrator-api-v4';

const PATCH=String.raw`
<style id="ss-v9-style">
#ss-v9-health{margin:0 0 15px}.v9{border:1px solid #294863;border-radius:14px;background:linear-gradient(180deg,#10263a,#091827);padding:13px;color:#eef7ff}.v9h{display:flex;justify-content:space-between;gap:10px;align-items:center}.v9h b{font-size:13px}.v9h small{color:#91a8c4}.v9grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:7px;margin-top:10px}.v9k{border:1px solid #213c56;border-radius:9px;padding:8px;background:#0b1d2e}.v9k small{display:block;color:#8099b0;font-size:8px}.v9k strong{display:block;font-size:17px}.v9api{display:flex;gap:6px;flex-wrap:wrap}.v9pill{border:1px solid #39526d;border-radius:999px;padding:4px 7px;font-size:8px}.v9ok{border-color:#287759;color:#78ecb6}.v9bad{border-color:#7b3945;color:#ffa0aa}.v9warn{border-color:#735d30;color:#ffd77c}.v9note{font-size:8px;color:#8099b0;margin-top:7px}
@media(max-width:1000px){.v9grid{grid-template-columns:repeat(3,1fr)}}@media(max-width:650px){.v9grid{grid-template-columns:repeat(2,1fr)}}
</style>
<script id="ss-v9-script">
(function(){
var SB='https://rpfadpdnnxequgvdcfoq.supabase.co',KEY='sb_publishable_NkMSCtURWbZcA8MCY1H5sA_W_G10WYD',ADMIN=SB+'/functions/v1/socialscheduler-admin-api',ORCH=SB+'/functions/v1/socialscheduler-orchestrator-api-v4';
var D=null,O=null,EA='',EO='',loading=false,last=0;
function e(v){return String(v==null?'':v).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
function n(v){return Number(v||0)}
function session(){try{return JSON.parse(localStorage.getItem('ss_session')||'null')}catch(_){return null}}
async function call(url,action){var s=session();if(!s||!s.access_token)throw new Error('admin session required');var r=await fetch(url,{method:'POST',headers:{apikey:KEY,authorization:'Bearer '+s.access_token,'content-type':'application/json'},body:JSON.stringify({action:action})}),j=await r.json().catch(function(){return{error:'invalid response'}});if(!r.ok||j.ok===false)throw new Error(j.error||('HTTP '+r.status));return j}
function host(){var h=document.querySelector('#ss-v9-health');if(!h){h=document.createElement('div');h.id='ss-v9-health';var c=document.querySelector('#content');if(c&&c.parentNode)c.parentNode.insertBefore(h,c)}return h}
function currentPipeline(p){if(!D)return 0;var q=(D.queue||[]).filter(function(x){return x.platform===p&&['approved','leased','scheduled'].includes(x.status)}).reduce(function(a,x){return a+n(x.jobs)},0);var h=(D.delivery_history||[]).filter(function(x){return x.platform===p&&x.status==='scheduled'}).reduce(function(a,x){return a+n(x.jobs)},0);return q+h}
function render(){var h=host(),s=D&&D.summary||{},a=D&&D.autopilot_state||{},adminOk=!!D,orchOk=!!O,products=n(s.product_rankings),fb=n(s.feedback_rows),dec=n(s.orchestration_decisions),rt=n(s.runtime_snapshots),ai=n(s.ai_calls_2d);var critical=products===0;h.innerHTML='<div class="v9"><div class="v9h"><div><b>Production Audit · v9</b><small> · smart fill + fresh-product weighting + posted-feedback learning</small></div><div class="v9api"><span class="v9pill '+(adminOk?'v9ok':'v9bad')+'">Admin '+(adminOk?'OK':'ERROR')+'</span><span class="v9pill '+(orchOk?'v9ok':'v9bad')+'">Orchestrator '+(orchOk?'v4 OK':'ERROR')+'</span><span class="v9pill '+(critical?'v9bad':'v9ok')+'">Products '+(products||0)+'</span></div></div><div class="v9grid"><div class="v9k"><small>Facebook pipeline</small><strong>'+currentPipeline('facebook')+'</strong></div><div class="v9k"><small>Instagram pipeline</small><strong>'+currentPipeline('instagram')+'</strong></div><div class="v9k"><small>TikTok pipeline</small><strong>'+currentPipeline('tiktok')+'</strong></div><div class="v9k"><small>Feedback rows</small><strong>'+fb+'</strong></div><div class="v9k"><small>Decisions</small><strong>'+dec+'</strong></div><div class="v9k"><small>Runtime snapshots</small><strong>'+rt+'</strong></div></div><div class="v9note">Schedule coverage '+n(a.schedule_coverage_pct)+'% · AI calls ledger '+ai+' · '+(EA?'Admin: '+e(EA)+' · ':'')+(EO?'Orchestrator: '+e(EO)+' · ':'')+(critical?'CRITICAL: Product Intelligence still has zero durable rankings.':'Product Intelligence durable rankings available.')+'</div></div>'}
async function load(){if(loading)return;var s=session();if(!s||!s.access_token)return;loading=true;try{var r=await Promise.allSettled([call(ADMIN,'dashboard'),call(ORCH,'dashboard_plus')]);if(r[0].status==='fulfilled'){D=r[0].value;EA=''}else EA=String(r[0].reason&&r[0].reason.message||r[0].reason||'error');if(r[1].status==='fulfilled'){O=r[1].value;EO=''}else EO=String(r[1].reason&&r[1].reason.message||r[1].reason||'error');last=Date.now();render()}finally{loading=false}}
function tick(){var app=document.querySelector('#app');var h=document.querySelector('#ss-v9-health');if(!app||app.classList.contains('hidden')){if(h)h.style.display='none';return}if(h)h.style.display='block';if(!D||Date.now()-last>45000)load()}
document.addEventListener('click',function(ev){var t=ev.target;if(t&&t.closest&&t.closest('.nav button'))setTimeout(tick,50)});setInterval(tick,5000);setTimeout(tick,900);
})();
</script>`;

export default {
  async fetch(request,env,ctx){
    var url=new URL(request.url);
    if(url.pathname==='/health')return new Response(JSON.stringify({ok:true,service:'socialscheduler-autopilot',version:'9.0',orchestrator:'v4',resilient_partial_ui:true,smart_fill:'v4',feedback_learning:true}),{headers:{'content-type':'application/json','cache-control':'no-store'}});
    var response=await base.fetch(request,env,ctx);
    var type=response.headers.get('content-type')||'';
    if(!type.includes('text/html'))return response;
    var html=await response.text();
    html=html.split(ORCH_OLD).join(ORCH_NEW);
    html=html.replace('</body>',PATCH+'</body>');
    var headers=new Headers(response.headers);headers.set('cache-control','no-store');
    return new Response(html,{status:response.status,statusText:response.statusText,headers});
  }
};
