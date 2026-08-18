import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { createApp } from "../src/app.js";

let server;
let baseUrl;

before(async () => {
  const app = createApp();
  await new Promise((resolve) => {
    server = app.listen(0, () => {
      const { port } = server.address();
      baseUrl = `http://127.0.0.1:${port}`;
      resolve();
    });
  });
});

after(() => {
  server.close();
});

test("health endpoint responds ok", async () => {
  const res = await fetch(`${baseUrl}/api/health`);
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { status: "ok" });
});

test("menu lists dishes with formatted prices", async () => {
  const res = await fetch(`${baseUrl}/api/menu`);
  assert.equal(res.status, 200);
  const menu = await res.json();
  assert.ok(menu.length >= 1);
  assert.match(menu[0].price, /^\$\d+\.\d{2}$/);
});

test("placing a valid order returns a confirmation", async () => {
  const res = await fetch(`${baseUrl}/api/orders`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dishId: "penne-arrabbiata", quantity: 2 }),
  });
  assert.equal(res.status, 201);
  const order = await res.json();
  assert.equal(order.quantity, 2);
  assert.equal(order.total, "$28.00");
  assert.match(order.message, /Order received/);
});

test("ordering an unknown dish is rejected", async () => {
  const res = await fetch(`${baseUrl}/api/orders`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dishId: "nope" }),
  });
  assert.equal(res.status, 400);
});
