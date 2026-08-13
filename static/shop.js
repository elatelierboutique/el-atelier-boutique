
const WA = "573147693962";
let products = [], activeCat = "Todos";
let cart = JSON.parse(localStorage.getItem("atelierCartV4") || "[]");
let currentProduct = null, selectedSize = "", selectedColor = "", modalQty = 1, currentImageIndex = 0;
const imgUrl = p => (String(p||"").startsWith("http") ? p : "/static/"+p);
const money = n => new Intl.NumberFormat("es-CO",{style:"currency",currency:"COP",maximumFractionDigits:0}).format(n);
const $ = sel => document.querySelector(sel);

function colorHex(name){
  const n=(name||"").toLowerCase();
  const map={
    "beige":"#e7d1b5","negro":"#111111","marfil":"#f4eee3","café":"#9a5b36","cafe":"#9a5b36",
    "rosa":"#e7b4c0","rosa palo":"#cfaeac","azul cielo":"#9dc0db","azul denim":"#4e7ca5",
    "blanco":"#ffffff","vinotinto":"#6f1d31","verde":"#4f7868","gris":"#8e95a3"
  };
  return map[n] || "#d8d8d8";
}
async function loadProducts(){
  products = await fetch("/api/products").then(r=>r.json());
  renderProducts(); renderCart();
}
function renderProducts(){
  const q=$("#searchInput").value.trim().toLowerCase();
  const list=products.filter(p => (activeCat==="Todos"||p.category===activeCat) && `${p.name} ${p.subtitle} ${p.description}`.toLowerCase().includes(q));
  $("#productGrid").innerHTML=list.map(p=>`
    <article class="productCard" onclick="openProduct(${p.id})">
      <div class="productImage">
        <img src="${imgUrl(p.image)}" alt="${p.name}">
        ${p.featured?'<span class="newTag">NUEVO</span>':''}
      </div>
      <div class="productInfo">
        <h3>${p.name}</h3>
        <p>${p.subtitle}</p>
        <div class="productMeta">
          <span class="productPrice">${money(p.price)}</span>
          <span class="productSizes">${p.sizes.join(" · ")}</span>
        </div>
      </div>
    </article>`).join("");
}
window.openProduct=id=>{
  currentProduct=products.find(p=>p.id===id);
  selectedSize="";selectedColor="";modalQty=1;currentImageIndex=0;
  $("#modalName").textContent=currentProduct.name;
  $("#modalPrice").textContent=money(currentProduct.price);
  $("#modalDescription").textContent=currentProduct.description;
  $("#modalQty").textContent=1;
  $("#crumbName").textContent=currentProduct.name;
  $("#modalSizes").innerHTML=currentProduct.sizes.map(x=>`<button class="optBtn" onclick="chooseSize('${esc(x)}',this)">${x}</button>`).join("");
  $("#modalColors").innerHTML=currentProduct.colors.map(x=>`<button class="colorBtn" onclick="chooseColor('${esc(x)}',this)"><span class="swatch" style="background:${colorHex(x)}"></span><span>${x}</span></button>`).join("");
  renderGallery();
  renderRelated();
  $("#productModal").classList.add("open");
  $("#productModal").setAttribute("aria-hidden","false");
  document.body.style.overflow="hidden";
}
function esc(v){return v.replace(/'/g,"\\'")}
window.chooseSize=(v,el)=>{selectedSize=v;document.querySelectorAll("#modalSizes .optBtn").forEach(b=>b.classList.remove("active"));el.classList.add("active")}
window.chooseColor=(v,el)=>{
  selectedColor=v;document.querySelectorAll("#modalColors .colorBtn").forEach(b=>b.classList.remove("active"));el.classList.add("active");
  const idx=(currentProduct.gallery||[]).findIndex(g=>(g.color||"").toLowerCase()===v.toLowerCase());
  if(idx>=0){currentImageIndex=idx;renderGallery()}
}
function gallery(){
  return (currentProduct.gallery&&currentProduct.gallery.length)?currentProduct.gallery:[{image:currentProduct.image,color:""}];
}
function renderGallery(){
  const g=gallery();
  $("#modalMainImage").src=imgUrl(g[currentImageIndex].image);
  $("#modalMainImage").onclick=openLightbox;
  $("#modalThumbs").innerHTML=g.map((img,i)=>`
    <button class="thumb ${i===currentImageIndex?'active':''}" onclick="pickImage(${i})">
      <img src="${imgUrl(img.image)}">
      ${img.color?`<span>${img.color}</span>`:""}
    </button>`).join("");
}
window.pickImage=i=>{currentImageIndex=i;renderGallery()}
function renderRelated(){
  const list=products.filter(p=>p.id!==currentProduct.id).slice(0,4);
  $("#relatedProducts").innerHTML=list.map(p=>`
    <article class="related-card" onclick="openProduct(${p.id})">
      <img src="${imgUrl(p.image)}">
      <h4>${p.name}</h4>
      <span>${money(p.price)}</span>
    </article>`).join("");
}
function closeProduct(){
  $("#productModal").classList.remove("open");
  $("#productModal").setAttribute("aria-hidden","true");
  document.body.style.overflow="";
}
window.closeProduct=closeProduct;
$("#closeProduct").onclick=closeProduct;
$("#zoomImage").onclick=openLightbox;
function openLightbox(){
  const g=gallery();
  $("#lightbox").classList.add("open");
  renderLightbox();
}
function renderLightbox(){
  const g=gallery(),item=g[currentImageIndex];
  $("#lightboxImage").src=imgUrl(item.image);
  $("#lightColor").textContent=item.color||currentProduct.name;
  $("#lightCounter").textContent=`${currentImageIndex+1} / ${g.length}`;
  $("#lightboxThumbs").innerHTML=g.map((img,i)=>`
    <button class="lightboxThumb ${i===currentImageIndex?'active':''}" onclick="lightPick(${i})"><img src="${imgUrl(img.image)}"></button>`).join("");
}
window.lightPick=i=>{currentImageIndex=i;renderLightbox();renderGallery()}
$("#closeLightbox").onclick=()=>$("#lightbox").classList.remove("open");
$("#lightPrev").onclick=()=>{const g=gallery();currentImageIndex=(currentImageIndex-1+g.length)%g.length;renderLightbox();renderGallery()}
$("#lightNext").onclick=()=>{const g=gallery();currentImageIndex=(currentImageIndex+1)%g.length;renderLightbox();renderGallery()}
$("#qtyMinus").onclick=()=>{modalQty=Math.max(1,modalQty-1);$("#modalQty").textContent=modalQty}
$("#qtyPlus").onclick=()=>{modalQty=Math.min(9,modalQty+1);$("#modalQty").textContent=modalQty}
$("#modalAdd").onclick=()=>{
  if(!selectedSize){toast("Selecciona una talla");return}
  if(!selectedColor){toast("Selecciona un color");return}
  const key=`${currentProduct.id}|${selectedSize}|${selectedColor}`;
  const ex=cart.find(x=>x.key===key);
  if(ex) ex.qty=Math.min(9,ex.qty+modalQty); else cart.push({key,id:currentProduct.id,size:selectedSize,color:selectedColor,qty:modalQty});
  saveCart();toast("Agregado a tu carrito");
}
function saveCart(){localStorage.setItem("atelierCartV4",JSON.stringify(cart));renderCart()}
function renderCart(){
  const count=cart.reduce((sum,x)=>sum+x.qty,0);
  $("#cartBadge").textContent=count;
  $("#stickyCountText").textContent=`${count} producto${count===1?"":"s"}`;
  const total=cart.reduce((sum,i)=>{const p=products.find(x=>x.id===i.id);return sum+(p?p.price*i.qty:0)},0);
  $("#stickyTotal").textContent=money(total);
  $("#stickyThumbs").innerHTML=cart.slice(0,5).map(i=>{const p=products.find(x=>x.id===i.id);return p?`<img src="${imgUrl(p.image)}">`:""}).join("");

  if(!cart.length){
    $("#cartItems").innerHTML="";
    $("#emptyCart").classList.remove("hidden");
    $("#cartFormWrap").classList.add("hidden");
    return
  }
  $("#emptyCart").classList.add("hidden");
  $("#cartFormWrap").classList.remove("hidden");
  $("#cartItems").innerHTML=cart.map(i=>{const p=products.find(x=>x.id===i.id);if(!p)return"";return`
    <div class="cartItem">
      <img src="${imgUrl(p.image)}">
      <div><h4>${p.name}</h4><p>${p.ref} · ${i.size} · ${i.color}</p>
      <div class="qtyLine"><button onclick="chg('${i.key}',-1)">−</button><b>${i.qty}</b><button onclick="chg('${i.key}',1)">+</button><button class="remove" onclick="delItem('${i.key}')">Quitar</button></div></div>
      <b>${money(p.price*i.qty)}</b>
    </div>`}).join("");
  $("#subtotal").textContent=money(total);
}
window.chg=(key,d)=>{const item=cart.find(x=>x.key===key);if(!item)return;item.qty+=d;if(item.qty<=0)cart=cart.filter(x=>x.key!==key);if(item.qty>9)item.qty=9;saveCart()}
window.delItem=key=>{cart=cart.filter(x=>x.key!==key);saveCart()}
function openCart(){closeProduct();$("#drawer").classList.add("open");$("#overlay").classList.add("open");document.body.style.overflow="hidden"}
function closeCart(){$("#drawer").classList.remove("open");$("#overlay").classList.remove("open");document.body.style.overflow=""}
$("#openCart").onclick=openCart;$("#topCart").onclick=openCart;$("#stickyOpen").onclick=openCart;$("#closeCart").onclick=closeCart;$("#overlay").onclick=closeCart;
document.querySelectorAll(".chip").forEach(b=>b.onclick=()=>{document.querySelectorAll(".chip").forEach(x=>x.classList.remove("active"));b.classList.add("active");activeCat=b.dataset.cat;renderProducts()})
$("#searchInput").oninput=renderProducts;
const city=$("#city"),otherWrap=$("#otherCityWrap"),otherCity=$("#otherCity"),ship=$("#shippingInfo");
city.onchange=()=>{const other=city.value==="Otra ciudad";otherWrap.classList.toggle("hidden",!other);otherCity.required=other;ship.innerHTML=city.value==="Pasto"?"🚚 <b>Domicilio GRATIS en Pasto</b>":other?"📦 <b>+ envío</b> · valor por confirmar":"Selecciona tu ciudad."}
$("#orderForm").onsubmit=e=>{
  e.preventDefault();if(!cart.length)return;
  const name=$("#name").value.trim(),phone=$("#phone").value.trim(),ct=city.value==="Otra ciudad"?otherCity.value.trim():city.value,notes=$("#notes").value.trim();
  const total=cart.reduce((sum,i)=>{const p=products.find(x=>x.id===i.id);return sum+p.price*i.qty},0);
  const lines=cart.map((i,n)=>{const p=products.find(x=>x.id===i.id);return `${n+1}. *${p.name}*\n   Ref: ${p.ref}\n   Talla: ${i.size}\n   Color: ${i.color}\n   Cantidad: ${i.qty}\n   Valor: ${money(p.price*i.qty)}`}).join("\n\n");
  const msg=[`🛍️ *NUEVA SOLICITUD — EL ATELIER BOUTIQUE*`,``,`👤 *Cliente:* ${name}`,`📱 *Teléfono:* ${phone}`,`📍 *Ciudad:* ${ct}`,``,`*PRODUCTOS SOLICITADOS*`,lines,``,`💰 *Total productos:* ${money(total)}`,city.value==="Pasto"?"🚚 *Domicilio GRATIS en Pasto*":"📦 *+ envío · valor por confirmar*",notes?`📝 *Observaciones:* ${notes}`:"",``,`Solicitud pendiente de confirmación de disponibilidad.`,`Confirmación en un plazo de hasta 3 días.`,`Entrega estimada: hasta 5 días hábiles después de confirmar.`].filter(Boolean).join("\n");
  window.open(`https://wa.me/${WA}?text=${encodeURIComponent(msg)}`,"_blank");
}
function toast(t){const x=$("#toast");x.textContent=t;x.classList.add("show");clearTimeout(window.__tt);window.__tt=setTimeout(()=>x.classList.remove("show"),1800)}
document.addEventListener("keydown",e=>{if(e.key==="Escape"){$("#lightbox").classList.remove("open");closeProduct();closeCart()}})
loadProducts();
