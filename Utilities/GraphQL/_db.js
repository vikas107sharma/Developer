let games = [
  { id: "1", title: "Zelda, Tears of the Kingdom", platform: ["Switch"] },
  { id: "2", title: "Final Fantasy 7 Remake", platform: ["PS5", "Xbox"] },
  { id: "3", title: "Elden Ring", platform: ["PS5", "Xbox", "PC"] },
  { id: "4", title: "Mario Kart", platform: ["Switch"] },
  { id: "5", title: "Pokemon Scarlet", platform: ["PS5", "Xbox", "PC"] },
];

let authors = [
  { id: "1", name: "mario", verified: true },
  { id: "2", name: "yoshi", verified: false },
  { id: "3", name: "peach", verified: true },
];

let reviews = [
  {
    id: "1",
    rating: 9,
    content: "An incredible reimagining of a classic. The updated mechanics and visuals are stunning.",
    author_id: "1",
    game_id: "2" // Final Fantasy 7 Remake
  },
  {
    id: "2",
    rating: 10,
    content: "A breathtaking adventure through Hyrule. The open world and physics make it unforgettable.",
    author_id: "2",
    game_id: "1" // Zelda
  },
  {
    id: "3",
    rating: 7,
    content: "Challenging and rewarding. The world design and lore are top-notch.",
    author_id: "3",
    game_id: "3" // Elden Ring
  },
  {
    id: "4",
    rating: 5,
    content: "Fun in short bursts, but the gameplay can get repetitive over time.",
    author_id: "2",
    game_id: "4" // Mario Kart
  },
  {
    id: "5",
    rating: 8,
    content: "A fresh take on the classic Pokémon formula with great exploration elements.",
    author_id: "1",
    game_id: "5" // Pokemon Scarlet
  },
  {
    id: "6",
    rating: 7,
    content: "Solid combat and emotional story beats. A must-play for fans of the original.",
    author_id: "1",
    game_id: "2" // Final Fantasy 7 Remake
  },
  {
    id: "7",
    rating: 10,
    content: "One of the best games ever made. Pure freedom and creativity in gameplay.",
    author_id: "3",
    game_id: "1" // Zelda
  },
];


export {
    games,
    authors,
    reviews,
}