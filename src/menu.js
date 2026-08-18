export const menu = [
  {
    id: "spaghetti-carbonara",
    name: "Spaghetti Carbonara",
    description: "Guanciale, egg yolk, pecorino romano and black pepper.",
    priceCents: 1600,
  },
  {
    id: "penne-arrabbiata",
    name: "Penne all'Arrabbiata",
    description: "Garlic, tomato and a generous kick of chilli.",
    priceCents: 1400,
  },
  {
    id: "tagliatelle-al-ragu",
    name: "Tagliatelle al Ragù",
    description: "Slow-cooked beef and pork ragù, Bolognese style.",
    priceCents: 1800,
  },
  {
    id: "linguine-alle-vongole",
    name: "Linguine alle Vongole",
    description: "Fresh clams, white wine, parsley and garlic.",
    priceCents: 1900,
  },
];

export function findDish(id) {
  return menu.find((dish) => dish.id === id);
}

export function formatPrice(priceCents) {
  return `$${(priceCents / 100).toFixed(2)}`;
}
