const iconPaths={megaphone:'<path d="m3 9 14-5v16L3 15V9Zm14 1 4-2v8l-4-2M7 16l2 5h3l-2-4"/>',grid:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',bookmark:'<path d="M6 4h12v17l-6-4-6 4V4Z"/>',gamepad:'<path d="M8 7h8c3 0 4 2 5 8s-2 7-5 3l-1-1H9l-1 1c-3 4-6 3-5-3S5 7 8 7Z"/><path d="M7 10v5m-2-2.5h4m6-1h.01m3 3h.01"/>',message:'<path d="M5 4h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H9l-6 4V6a2 2 0 0 1 2-2Z"/><path d="M7 9h10M7 13h7"/>',plus:'<path d="M12 5v14M5 12h14"/>',refresh:'<path d="M20 7v5h-5M4 17v-5h5"/><path d="M19 11a7 7 0 0 0-12-5L4 9m1 4a7 7 0 0 0 12 5l3-3"/>',search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',star:'<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3l-5.6 2.9 1.1-6.2L3 9.6l6.2-.9L12 3Z"/>',eye:'<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',code:'<path d="m8 7-5 5 5 5m8-10 5 5-5 5M14 4l-4 16"/>',zap:'<path d="m13 2-9 12h7l-1 8 10-12h-7l1-8Z"/>',upload:'<path d="M12 16V3m-5 5 5-5 5 5M4 15v5h16v-5"/>',reply:'<path d="m9 5-6 6 6 6m-6-6h10c5 0 8 3 8 8"/>',check:'<path d="m5 12 4 4L19 6"/>',inbox:'<path d="M4 4h16v16H4V4Z"/><path d="M4 13h5l1 3h4l1-3h5"/>'};
function icon(name){return `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${iconPaths[name]||iconPaths.message}</svg>`}
function hydrateIcons(root=document){root.querySelectorAll('[data-icon]').forEach(el=>el.innerHTML=icon(el.dataset.icon))}hydrateIcons();
let user=null,authMode='login',authReturn=null,returnReview=null,reviewRating=0,feedbackData={games:[],reviews:[]},feedbackTab='all',feedbackPreview=true,feedbackRequest=0;
const originalShow=show;
const viewPaths={feed:'/',saved:'/saved',studio:'/studio',feedback:'/feedback',marketing:'/marketing',auth:'/login'};
show=function(v,{replace=false,historyChange=true}={}){
  if(v==='marketing'&&user?.role!=='developer'){if(!user){openAuth('login','developer','marketing');return}else{toast('Promotion is available to developer accounts.');v='feed'}}if(!['feed','saved','studio','feedback','marketing','auth'].includes(v))v='feed';
  originalShow(v);
  const path=v==='auth'?'/'+authMode:viewPaths[v];
  if(historyChange&&location.pathname!==path)history[replace?'replaceState':'pushState']({},'',path);
  const titles={feed:['Discover','your next obsession.'],saved:['Saved games','Your next round is waiting.'],studio:['Developer studio','Small demos. Big possibilities.'],feedback:['Player feedback','Make your next version better.'],marketing:['Promote your game','Put your next great idea in the spotlight.'],auth:['The QuickPlay community','Come for a game. Stay for the possibilities.']};
  const title=titles[v];$('.header-title').innerHTML=`${title[0]} <span>${title[1]}</span>`;
  document.title=(v==='auth'?(authMode==='signup'?'Sign up':'Log in'):title[0])+' — QuickPlay';
  if(v==='studio')updateStudioGate();
  if(v==='feedback')loadFeedback();if(v==='marketing')loadMarketing();
  window.scrollTo({top:0,behavior:'instant'});
};
function openAuth(mode='login',role='player',destination=null){
  authMode=mode==='signup'?'signup':'login';
  if(destination)authReturn=destination;
  $('#auth-form').reset();$('#auth-status').textContent='';
  $('#auth-form').elements.role.value=role;
  const signup=authMode==='signup';
  $('#role-fields').classList.toggle('hidden',!signup);$('#role-fields').disabled=!signup;
  $('#name-field').classList.toggle('hidden',!signup);$('#auth-form').elements.name.required=signup;
  $('#auth-form').elements.password.minLength=signup?8:1;
  $('#auth-form').elements.password.autocomplete=signup?'new-password':'current-password';
  $('#auth-form').elements.password.placeholder=signup?'Create a password':'Your password';
  $('#password-hint').classList.toggle('hidden',!signup);
  $('#auth-eyebrow').textContent=signup?'A GOOD PLACE TO START':'WELCOME BACK';
  $('#auth-title').textContent=signup?'Find your people. And your games.':'Ready for another round?';
  $('#auth-description').textContent=signup?'A player, a creator, or a little of both. You belong here.':'Log in to pick up where you left off.';
  $('#auth-submit').innerHTML=(signup?'Create account':'Log in')+' <span>→</span>';
  $('#login-tab').classList.toggle('selected',!signup);$('#signup-tab').classList.toggle('selected',signup);
  $('#auth-switch-text').textContent=signup?'Already part of the community?':'New to QuickPlay?';
  $('#auth-switch-button').dataset.auth=signup?'login':'signup';$('#auth-switch-button').textContent=signup?'Log in →':'Create an account ↗';
  $('#auth-form').elements.password.type='password';$('#toggle-password').setAttribute('aria-label','Show password');$('#toggle-password').setAttribute('aria-pressed','false');
  show('auth');
}
document.addEventListener('click',e=>{const b=e.target.closest('[data-auth]');if(!b)return;const role=b.dataset.role||$('#auth-form').elements.role.value||'player';openAuth(b.dataset.auth,role,b.dataset.return||null)});
$('#toggle-password').onclick=()=>{const input=$('#auth-form').elements.password,visible=input.type==='password';input.type=visible?'text':'password';$('#toggle-password').setAttribute('aria-label',visible?'Hide password':'Show password');$('#toggle-password').setAttribute('aria-pressed',String(visible))};
$('#auth-form').onsubmit=async e=>{
  e.preventDefault();const form=e.target,button=$('#auth-submit'),mode=authMode;button.disabled=true;$('#auth-status').textContent='';button.textContent=mode==='signup'?'Creating your account…':'Logging in…';
  try{const data=new FormData(form);const result=await api('/api/auth/'+mode,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:data.get('email'),password:data.get('password'),name:data.get('name'),role:data.get('role')})});user=result.user;form.reset();updateAccount();await refreshFeed();const destination=authReturn||(user.role==='developer'?'studio':'feed');authReturn=null;show(destination);toast(mode==='signup'?'Welcome to QuickPlay, '+user.name+'!':'Welcome back, '+user.name);if(returnReview){const id=returnReview;returnReview=null;await openComments(id)}}catch(error){$('#auth-status').textContent=error.message}finally{button.disabled=false;button.innerHTML=(authMode==='signup'?'Create account':'Log in')+' <span>→</span>'}
};
function updateAccount(){
  const box=$('#account-actions');
  if(!user){box.innerHTML='<button class="text-button" data-auth="login">Log in</button><button class="primary compact" data-auth="signup">Sign up <span>↗</span></button>'}else{box.innerHTML=`<div class="account-chip"><span class="account-avatar">${escapeHTML(user.name.slice(0,2).toUpperCase())}</span><div><b>${escapeHTML(user.name)}</b><small>${user.role==='developer'?'Developer':'Player'}</small></div></div><button class="text-button logout-button" id="logout">Log out</button>`;$('#logout').onclick=async()=>{try{await api('/api/auth/logout',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});user=null;authReturn=null;returnReview=null;feedbackRequest++;marketingRequest++;marketingData={plans:[],games:[],campaigns:[]};feedbackData={games:[],reviews:[]};$('#unread-count').classList.add('hidden');updateAccount();if(view==='feedback')await loadFeedback();if(view==='studio')renderStats();if(view==='marketing')show('feed');$('#promotion-checkout').close();toast('You’re logged out. See you next round.')}catch(e){toast(e.message)}}}
  $('#marketing-nav').classList.toggle('hidden',user?.role!=='developer');$('.side-community [data-auth]').classList.toggle('hidden',!!user);updateStudioGate();updateReviewGate();
}
function updateStudioGate(){
  const developer=user?.role==='developer';$('#upload-fields').disabled=!developer;
  $('#studio-gate').classList.toggle('hidden',developer);
  if(!user)$('#studio-gate').innerHTML='Your demo deserves an audience. <button class="text-button" data-auth="signup" data-role="developer" data-return="studio">Create a developer account ↗</button> or <button class="text-button" data-auth="login" data-return="studio">log in</button> to publish.';
  else if(!developer)$('#studio-gate').textContent='You’re signed in as a player. Uploads and the private feedback inbox are available to developer accounts.';
  else if(!$('#submission').elements.studio.value)$('#submission').elements.studio.value=user.name;
}
renderStats=function(){
  const owned=user?.role==='developer'?games.filter(g=>g.owner_id===user.id):[],values=owned.map(g=>stats[g.id]);
  $('#metrics').innerHTML=`<div class="metric">Your demos<strong>${owned.length}</strong></div><div class="metric">Demo starts this session<strong>${values.reduce((a,s)=>a+s.starts,0)}</strong></div><div class="metric">Time played this session<strong>${Math.floor(values.reduce((a,s)=>a+s.seconds,0))}s</strong></div>`;
  $('#performance').innerHTML=owned.length?owned.map(g=>`<div class="performance-row"><div>${escapeHTML(g.title)}<br><small>${escapeHTML(g.genre)} · Live in the feed</small></div><div>${stats[g.id].starts} plays<br><button class="text-button" data-play="${escapeHTML(g.id)}">Play demo ↗</button></div></div>`).join(''):'<div class="feedback-empty"><span>↗</span><h3>Your first demo starts here.</h3><p>Upload a self-contained HTML game. Players can try it instantly and send you feedback.</p></div>';
  $('#performance').querySelectorAll('[data-play]').forEach(b=>b.onclick=()=>start(b.dataset.play));updateStudioGate();
};
function updateReviewGate(){
  const gate=$('#review-auth-gate');gate.classList.toggle('hidden',!!user);$('#review-fields').disabled=!user;
  if(!user)gate.innerHTML='Played a round? <button type="button" class="text-button" id="review-login">Log in to leave a review ↗</button>';
  const button=$('#review-login');if(button)button.onclick=()=>{returnReview=commentGame;authReturn='feed';$('#comments-dialog').close();openAuth('login')};
}
document.querySelectorAll('[data-rating]').forEach(b=>b.onclick=()=>{reviewRating=Number(b.dataset.rating);document.querySelectorAll('[data-rating]').forEach(star=>{star.classList.toggle('selected',Number(star.dataset.rating)<=reviewRating);star.setAttribute('aria-pressed',String(Number(star.dataset.rating)===reviewRating))});$('#rating-label').textContent=['','Needs work','Could be better','Good start','Really enjoyed it','Loved it!'][reviewRating]});
function resetRating(){reviewRating=0;document.querySelectorAll('[data-rating]').forEach(b=>{b.classList.remove('selected');b.setAttribute('aria-pressed','false')});$('#rating-label').textContent='Choose a rating'}
function stars(rating){if(!rating)return '<span class="muted">Unrated</span>';return `<span aria-label="${rating} out of 5 stars">${'★'.repeat(rating)}<span class="dim-star">${'★'.repeat(5-rating)}</span></span>`}
function displayDate(value){return new Date(value.includes('T')?value:value.replace(' ','T')+'Z').toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'})}
function sampleFeedback(){
  const samples=[['Alex Chen','orbit',5,'Gameplay','The movement feels so good. I went in for one quick try and ended up playing five rounds. Would love to see more enemy types as the difficulty ramps up!',false],['Maya Rivers','neon',4,'Visuals','The neon palette and the sense of speed are a perfect match. A bit more contrast on the obstacles would help when things get fast.',false],['Jamie Park','prism',5,'Gameplay','Such a satisfying little puzzle. The feedback on a correct match is great — this is exactly the kind of game I’d keep coming back to.',false],['Sam Wilson','orbit',4,'Bug report','Had a great time, but the ship sometimes jumps when I drag close to the edge. It happened twice after restarting the demo.',false],['Riley Brooks','neon',5,'General','Instantly hooked. The controls are easy to pick up, and the art direction has so much personality. Excited to see where this goes.',true],['Jordan Lee','prism',4,'Suggestion','A colorblind mode would be a lovely addition. Maybe each color could have a different shape or pattern too?',true],['Taylor Morgan','orbit',5,'Visuals','Love the quiet space backdrop. It makes the action easy to follow. The tiny ship is surprisingly full of character.',true],['Casey Ellis','neon',4,'Gameplay','The lane switching is snappy and fun. A little warning before the next obstacle appears could make the first round more welcoming.',true]];
  return {games:games.filter(g=>['orbit','neon','prism'].includes(g.id)),reviews:samples.map((r,i)=>({id:'sample-'+i,name:r[0],game_id:r[1],game_title:games.find(g=>g.id===r[1]).title,studio:games.find(g=>g.id===r[1]).studio,rating:r[2],category:r[3],body:r[4],created:new Date(Date.now()-i*86400000-3600000).toISOString(),read_at:r[5]?'read':null,reply:i===4?'Thanks for playing! We’re working on more tracks for the next demo. Stay tuned.':null}))};
}
async function loadFeedback(){
  const request=++feedbackRequest;
  $('#feedback-notice').classList.remove('hidden');
  if(!user){feedbackPreview=true;feedbackData=sampleFeedback();$('#feedback-notice').innerHTML='<span><b>PREVIEW WORKSPACE</b> Explore a sample inbox. Your games, your players, your feedback.</span><button class="text-button" data-auth="signup" data-role="developer" data-return="feedback">Create your developer account ↗</button>';renderFeedback(true);return}
  feedbackPreview=false;
  if(user.role!=='developer'){feedbackData={games:[],reviews:[]};$('#feedback-notice').innerHTML='<span>Developer workspace · You’re signed in with a player account. Discover a game and share your thoughts.</span><button class="text-button" id="back-to-games">Explore games ↗</button>';$('#back-to-games').onclick=()=>show('feed');renderFeedback(true);return}
  $('#feedback-notice').classList.add('hidden');$('#feedback-list').innerHTML='<div class="feedback-empty"><p>Loading your feedback…</p></div>';
  try{const result=await api('/api/feedback');if(request!==feedbackRequest||!user||user.role!=='developer')return;feedbackData=result;renderFeedback(true)}catch(error){if(request!==feedbackRequest)return;feedbackData={games:[],reviews:[]};renderFeedback(true);$('#feedback-list').innerHTML=`<div class="feedback-empty"><span>↻</span><h3>Couldn’t load your feedback.</h3><p>${escapeHTML(error.message)}</p><button class="primary" id="retry-feedback">Try again</button></div>`;$('#retry-feedback').onclick=loadFeedback}
}
function renderFeedback(resetGames=false){
  const reviews=feedbackData.reviews,rated=reviews.filter(r=>r.rating),average=rated.length?(rated.reduce((a,r)=>a+r.rating,0)/rated.length).toFixed(1):'—',unread=reviews.filter(r=>!r.read_at).length,replied=reviews.filter(r=>r.reply).length;
  $('#feedback-metrics').innerHTML=[['Total reviews',reviews.length,'Every player’s perspective','message'],['Average rating',average+(rated.length?' <small>/ 5</small>':''),'From '+rated.length+' rated reviews','star'],['Unread feedback',unread,'New thoughts to explore','inbox'],['Games in your inbox',feedbackData.games.length,'Your playable demos','gamepad']].map((m,i)=>`<div class="feedback-metric ${i===1||i===2?'accent':''}"><div class="metric-top">${m[0]}${icon(m[3])}</div><strong>${m[1]}</strong><span class="metric-caption">${m[2]}</span></div>`).join('');
  $('#review-total').textContent=reviews.length;$('#tab-all').textContent=reviews.length;$('#tab-unread').textContent=unread;$('#tab-replied').textContent=replied;
  $('#unread-count').textContent=unread;$('#unread-count').classList.toggle('hidden',!unread||feedbackPreview);
  if(resetGames){const previous=$('#feedback-game').value;$('#feedback-game').innerHTML='<option value="all">All games</option>'+feedbackData.games.map(g=>`<option value="${escapeHTML(g.id)}">${escapeHTML(g.title)}</option>`).join('');if(feedbackData.games.some(g=>g.id===previous))$('#feedback-game').value=previous}
  $('#rating-summary').innerHTML=`<div class="rating-summary"><strong>${average}</strong><div><div class="review-rating">${rated.length?stars(Math.round(Number(average))):'☆☆☆☆☆'}</div><small>Based on ${rated.length} reviews</small></div></div>`;
  $('#rating-bars').innerHTML=[5,4,3,2,1].map(rating=>{const count=rated.filter(r=>r.rating===rating).length;return `<div class="rating-bar"><span>${rating} ★</span><div class="bar-track"><span style="width:${rated.length?count/rated.length*100:0}%"></span></div><span>${count}</span></div>`}).join('');
  $('#category-summary').innerHTML=['Gameplay','Visuals','Bug report','Suggestion','General'].map(category=>`<div class="category-row"><i></i><span>${category}</span><b>${reviews.filter(r=>r.category===category).length}</b></div>`).join('');
  renderReviewList();
}
function renderReviewList(){
  const query=$('#feedback-search').value.trim().toLowerCase(),game=$('#feedback-game').value,sort=$('#feedback-sort').value;
  const filtered=feedbackData.reviews.filter(r=>(game==='all'||r.game_id===game)&&(feedbackTab==='all'||(feedbackTab==='unread'?!r.read_at:!!r.reply))&&[r.name,r.body,r.game_title,r.category,r.reply||''].join(' ').toLowerCase().includes(query));
  filtered.sort((a,b)=>sort==='highest'?(b.rating||0)-(a.rating||0):sort==='lowest'?(a.rating||0)-(b.rating||0):sort==='oldest'?a.created.localeCompare(b.created):b.created.localeCompare(a.created));
  const box=$('#feedback-list');
  if(!filtered.length){const noGames=!feedbackData.games.length;box.innerHTML=`<div class="feedback-empty"><span>${noGames?'↗':'✦'}</span><h3>${user?.role==='player'?'Keep the conversation going.':noGames?'Your next great idea starts with a play.':feedbackData.reviews.length?'No reviews match this view.':'The first play is just the beginning.'}</h3><p>${user?.role==='player'?'Try a demo and leave a review. Your feedback helps its developer build a better game.':noGames?'Publish your first demo, then come back here to see what players think.':feedbackData.reviews.length?'Try another game, change the search, or switch to all reviews.':'Share your demo with players. Their ratings, ideas, and bug reports will appear here.'}</p>${noGames?'<button class="primary" id="empty-action">'+(user?.role==='player'?'Discover games':'Upload your first demo')+' ↗</button>':feedbackData.reviews.length?'<button class="text-button" id="clear-filters">Clear filters ↻</button>':''}</div>`;const action=$('#empty-action');if(action)action.onclick=()=>show(user?.role==='player'?'feed':'studio');const clear=$('#clear-filters');if(clear)clear.onclick=()=>{$('#feedback-search').value='';$('#feedback-game').value='all';feedbackTab='all';updateTabs();renderReviewList()}}
  else box.innerHTML=filtered.map((r,i)=>`<article class="review-card ${!r.read_at?'unread':''}" data-review="${escapeHTML(r.id)}"><div class="review-top"><span class="review-avatar avatar-${i%4}">${escapeHTML(r.name.split(/\s+/).map(n=>n[0]).slice(0,2).join('').toUpperCase())}</span><div class="review-identity"><b>${escapeHTML(r.name)}</b><time datetime="${escapeHTML(r.created)}">${displayDate(r.created)}</time></div><div class="review-rating">${stars(r.rating)}</div></div><div class="review-meta"><span class="review-game">${icon('gamepad')}${escapeHTML(r.game_title)}</span><span class="category-chip ${r.category==='Bug report'?'bug':r.category==='Visuals'?'visuals':''}">${escapeHTML(r.category||'General')}</span>${!r.read_at?'<span class="unread-indicator">Unread</span>':''}</div><p class="review-body">${escapeHTML(r.body)}</p>${r.reply?`<div class="developer-reply"><b>${escapeHTML(r.studio||'Your studio')} · Developer reply</b><p>${escapeHTML(r.reply)}</p></div>`:''}<div class="review-actions"><button data-feedback-action="reply">${icon('reply')}${r.reply?'Edit reply':'Reply to player'}</button><button data-feedback-action="read">${icon(r.read_at?'inbox':'check')}${r.read_at?'Mark as unread':'Mark as read'}</button></div></article>`).join('');
  $('#feedback-footer').textContent=filtered.length?`Showing ${filtered.length} of ${feedbackData.reviews.length} reviews${feedbackPreview?' · Sample data':''}`:'Your players’ voices belong here.';
}
function updateTabs(){document.querySelectorAll('[data-review-tab]').forEach(b=>b.classList.toggle('selected',b.dataset.reviewTab===feedbackTab))}
document.querySelectorAll('[data-review-tab]').forEach(b=>b.onclick=()=>{feedbackTab=b.dataset.reviewTab;updateTabs();renderReviewList()});
$('#feedback-search').oninput=renderReviewList;$('#feedback-game').onchange=renderReviewList;$('#feedback-sort').onchange=renderReviewList;
$('#refresh-feedback').onclick=async()=>{const button=$('#refresh-feedback');button.disabled=true;try{await loadFeedback()}finally{button.disabled=false}};
$('#feedback-list').addEventListener('click',async e=>{
  const button=e.target.closest('[data-feedback-action]');if(!button)return;
  if(feedbackPreview){authReturn='feedback';openAuth('signup','developer');return}
  const card=button.closest('[data-review]'),review=feedbackData.reviews.find(r=>r.id===card.dataset.review);if(!review)return;
  if(button.dataset.feedbackAction==='read'){button.disabled=true;try{await api('/api/feedback/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reviewId:review.id,read:!review.read_at})});review.read_at=review.read_at?null:new Date().toISOString();renderFeedback();toast(review.read_at?'Marked as read':'Marked as unread')}catch(error){toast(error.message);button.disabled=false}return}
  if(card.querySelector('.reply-form')){card.querySelector('textarea').focus();return}
  const form=document.createElement('form');form.className='reply-form';form.innerHTML=`<label>Your reply<textarea name="reply" required maxlength="1000" rows="3" placeholder="Thank them, share an update, or ask a question…">${escapeHTML(review.reply||'')}</textarea></label><button class="primary" type="submit">Send reply ↗</button><button class="text-button" type="button">Cancel</button><p class="reply-status" role="status"></p>`;form.querySelector('[type="button"]').onclick=()=>form.remove();form.onsubmit=async event=>{event.preventDefault();const submit=form.querySelector('[type="submit"]');submit.disabled=true;try{const reply=form.elements.reply.value;await api('/api/feedback/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reviewId:review.id,reply})});review.reply=reply.trim();review.read_at=new Date().toISOString();renderFeedback();toast('Reply posted. Thanks for keeping the conversation going.')}catch(error){form.querySelector('.reply-status').textContent=error.message;submit.disabled=false}};card.append(form);form.querySelector('textarea').focus();
});
function routeFromLocation(){const path=location.pathname;if(path==='/signup'||path==='/login'){const next=new URLSearchParams(location.search).get('next');openAuth(path.slice(1),next==='marketing'?'developer':'player',next==='marketing'?'marketing':null);return}show(Object.keys(viewPaths).find(key=>viewPaths[key]===path)||'feed',{historyChange:false})}
window.addEventListener('popstate',routeFromLocation);
(async()=>{try{user=(await api('/api/auth/me')).user}catch(error){toast(error.message)}updateAccount();routeFromLocation()})();
let marketingData={plans:[],games:[],campaigns:[]},chosenPlan=null,marketingRequest=0;
function money(cents){return '$'+(cents/100).toFixed(cents%100?2:0)}
async function loadMarketing(){
  if(user?.role!=='developer')return;const request=++marketingRequest;
  $('#promotion-plans').innerHTML='<p class="muted">Loading visibility plans…</p>';
  try{const result=await api('/api/marketing');if(request!==marketingRequest||user?.role!=='developer')return;marketingData=result;renderMarketing()}catch(error){if(request!==marketingRequest)return;$('#promotion-plans').innerHTML=`<div class="feedback-empty"><h3>Couldn’t load promotion plans.</h3><p>${escapeHTML(error.message)}</p><button class="primary" id="retry-marketing">Try again</button></div>`;$('#retry-marketing').onclick=loadMarketing}
}
function renderMarketing(){
  $('#promotion-plans').innerHTML=marketingData.plans.map((p,i)=>`<article class="promotion-plan ${i===1?'recommended':''}">${i===1?'<span class="recommended-label">A GOOD PLACE TO START</span>':''}<span class="plan-mark">${['✧','✦','☀'][i]}</span><h3>${escapeHTML(p.name)}</h3><p>${escapeHTML(p.description)}</p><div class="plan-price">${money(p.amount)}<small>demo price</small></div><div class="plan-duration">${p.days} days of priority visibility</div><div class="plan-features"><p>${icon('check')}Priority placement in the feed</p><p>${icon('check')}One playable demo</p><p>${icon('check')}Clearly labeled promotion</p><p>${icon('check')}Your usual player feedback inbox</p></div><button class="primary full-width" data-plan="${escapeHTML(p.id)}">Choose ${escapeHTML(p.name)} <span>↗</span></button></article>`).join('');
  document.querySelectorAll('[data-plan]').forEach(b=>b.onclick=()=>openCheckout(b.dataset.plan));
  $('#campaign-count').textContent=marketingData.campaigns.length;
  $('#campaign-list').innerHTML=marketingData.campaigns.length?marketingData.campaigns.map(c=>`<article class="campaign-row"><div><h3>${escapeHTML(c.title)}</h3><small>${escapeHTML(marketingData.plans.find(p=>p.id===c.plan)?.name||c.plan)} · Demo campaign</small></div><div><span class="campaign-state ${c.status}">${c.status==='active'?'● Active':'Ended'}</span></div><div>${money(c.amount)}<small>Demo price · $0 charged</small></div><div>${displayDate(c.expires)}<small>Campaign end date</small></div></article>`).join(''):'<div class="feedback-empty"><span>✦</span><h3>Your next audience is out there.</h3><p>Choose a visibility plan above to start a demo campaign. Your active and past promotions will appear here.</p></div>';
}
function openCheckout(planId){
  chosenPlan=marketingData.plans.find(p=>p.id===planId);if(!chosenPlan)return;
  if(!marketingData.games.length){toast('Publish your first demo before starting a promotion.');show('studio');return}
  const activeGames=new Set(marketingData.campaigns.filter(c=>c.status==='active').map(c=>c.game_id));
  const eligible=marketingData.games.filter(g=>!activeGames.has(g.id));
  if(!eligible.length){toast('All your demos have active promotions. Publish another demo or wait for a campaign to end.');return}
  $('#promotion-form').reset();$('#promotion-status').textContent='';
  $('#promotion-game').innerHTML=eligible.map(g=>`<option value="${escapeHTML(g.id)}">${escapeHTML(g.title)}</option>`).join('');
  $('#checkout-summary').innerHTML=`<div class="checkout-summary"><div><span>Visibility plan</span><b>${escapeHTML(chosenPlan.name)}</b></div><div><span>Duration</span><b>${chosenPlan.days} days</b></div><div><span>Demo price</span><b>${money(chosenPlan.amount)} USD</b></div><div class="checkout-total"><span>Charged today</span><b>$0 · Demo mode</b></div></div>`;
  $('#promotion-checkout').showModal();
}
$('#close-checkout').onclick=()=>$('#promotion-checkout').close();$('#promotion-checkout').onclick=e=>{if(e.target===$('#promotion-checkout'))$('#promotion-checkout').close()};
$('#promotion-form').onsubmit=async e=>{e.preventDefault();const button=$('#confirm-promotion');button.disabled=true;$('#promotion-status').textContent='Activating your demo campaign…';try{await api('/api/marketing/purchase',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({gameId:e.target.elements.gameId.value,planId:chosenPlan.id,confirmDemo:e.target.elements.confirmDemo.checked})});$('#promotion-checkout').close();await Promise.all([loadMarketing(),refreshFeed()]);toast('Demo campaign active. No money was charged.')}catch(error){$('#promotion-status').textContent=error.message}finally{button.disabled=false}};
$('#refresh-marketing').onclick=loadMarketing;
