import express from "express";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { menu, findDish, formatPrice } from "./menu.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export function createApp() {
  const app = express();
  app.use(express.json());
  app.use(express.static(path.join(__dirname, "..", "public")));

  app.get("/api/health", (_req, res) => {
    res.json({ status: "ok" });
  });

  app.get("/api/menu", (_req, res) => {
    res.json(
      menu.map((dish) => ({ ...dish, price: formatPrice(dish.priceCents) })),
    );
  });

  app.post("/api/orders", (req, res) => {
    const { dishId, quantity } = req.body ?? {};
    const dish = findDish(dishId);

    if (!dish) {
      return res.status(400).json({ error: `Unknown dish: ${dishId}` });
    }

    const qty = Number.isInteger(quantity) && quantity > 0 ? quantity : 1;
    const totalCents = dish.priceCents * qty;

    res.status(201).json({
      dish: dish.name,
      quantity: qty,
      total: formatPrice(totalCents),
      message: `Order received: ${qty} x ${dish.name}. Buon appetito!`,
    });
  });

  return app;
}
