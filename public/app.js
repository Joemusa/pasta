async function loadMenu() {
  const res = await fetch("/api/menu");
  const dishes = await res.json();
  const menuEl = document.getElementById("menu");

  menuEl.innerHTML = dishes
    .map(
      (dish) => `
      <article class="dish">
        <h3>${dish.name}</h3>
        <p>${dish.description}</p>
        <div class="row">
          <span class="price">${dish.price}</span>
          <button data-id="${dish.id}" data-name="${dish.name}">Order</button>
        </div>
      </article>`,
    )
    .join("");

  menuEl.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => placeOrder(btn.dataset.id));
  });
}

async function placeOrder(dishId) {
  const res = await fetch("/api/orders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dishId, quantity: 1 }),
  });
  const order = await res.json();

  const ticket = document.getElementById("ticket");
  const body = document.getElementById("ticket-body");
  ticket.hidden = false;
  body.textContent = `${order.message} Total: ${order.total}`;
}

loadMenu();
