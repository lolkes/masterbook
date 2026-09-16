let active = 'Все';
let categories = [];
let items = [];
const $ = s => document.querySelector(s);

function money(v){return v==null?'Цена договорная':new Intl.NumberFormat('ru-RU').format(Number(v))+' ₽'}
function escapeHtml(v){return String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
function escapeAttr(v){return escapeHtml(v)}

async function loadCategories(){
  const r=await fetch('/api/marketplace/categories');
  if(!r.ok)throw new Error('Не удалось загрузить категории');
  categories=await r.json();
  $('#categories').innerHTML=['Все',...categories.map(x=>x.name)].map(c=>`<button class="cat ${c===active?'active':''}" onclick="setCat(${JSON.stringify(c)})">${c}</button>`).join('');
  $('#category').innerHTML=categories.map(c=>`<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('');
}

async function loadListings(){
  const p=new URLSearchParams({q:$('#search').value.trim(),sort:$('#sort').value,limit:'100'});
  if(active!=='Все')p.set('category',active);
  const r=await fetch('/api/marketplace/listings?'+p);
  if(!r.ok)throw new Error('Не удалось загрузить объявления');
  items=await r.json();render();
}

function setCat(c){active=c;loadCategories().catch(()=>{});loadListings().catch(showError)}
function render(){
  $('#count').textContent=`${items.length} объявлений`;
  $('#listings').innerHTML=items.length?items.map(x=>`<article class="card" onclick="openListing(${x.id})">
    ${x.image_url?`<img class="photo" src="${escapeAttr(x.image_url)}" alt="" loading="lazy">`:'<div class="photo placeholder">MarketGo</div>'}
    <div class="body"><div class="price">${money(x.price)}</div><div class="title">${escapeHtml(x.title)}</div><div class="meta">${escapeHtml(x.city||'Город не указан')} · ${escapeHtml(x.seller_name)}</div>${x.category?`<div class="category-label">${escapeHtml(x.category)}</div>`:''}</div>
  </article>`).join(''):'<div class="empty">Ничего не найдено</div>';
}
function showError(e){$('#count').textContent='Ошибка загрузки';$('#listings').innerHTML='<div class="empty">Сервер пока недоступен. Обновите страницу.</div>';console.error(e)}
function openSell(){$('#sellModal').classList.remove('hidden')}
function closeSell(){$('#sellModal').classList.add('hidden')}

async function submitListing(e){
  e.preventDefault();const b=e.submitter;b.disabled=true;b.textContent='Публикуем…';
  try{
    const r=await fetch('/api/marketplace/listings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:$('#title').value,description:$('#description').value,price:$('#price').value?Number($('#price').value):null,category_id:Number($('#category').value),seller_name:$('#seller').value,seller_contact:$('#contact').value,city:$('#city').value,image_url:$('#image').value})});
    const data=await r.json();if(!r.ok)throw new Error(data.detail||'Ошибка публикации');
    e.target.reset();closeSell();active='Все';await loadCategories();await loadListings();alert('Объявление опубликовано!');
  }catch(err){alert(err.message)}finally{b.disabled=false;b.textContent='Опубликовать'}
}

async function openListing(id){
  try{const r=await fetch('/api/marketplace/listings/'+id);const x=await r.json();if(!r.ok)throw new Error(x.detail||'Объявление не найдено');alert(`${x.title}\n\n${money(x.price)}\n${x.description||''}\n\nПродавец: ${x.seller_name}\nКонтакт: ${x.seller_contact}`)}catch(e){alert(e.message)}
}

(async()=>{try{await loadCategories();await loadListings()}catch(e){showError(e)}})();
