// https://www.youtube.com/watch?v=5199E50O7SI&ab_channel=freeCodeCamp.org

import { ApolloServer } from "@apollo/server";
import { startStandaloneServer } from "@apollo/server/standalone";
import * as db from "./_db.js";

// types
import { typeDefs } from "./schema.js";

const resolvers = {
  Query: {
    games() {
      return db.games;
    },
    authors() {
      return db.authors;
    },
    reviews() {
      return db.reviews;
    },
    review(_, args) {
      return db.reviews.find((r) => r.id == args.id);
    },
    game(_, args) {
      return db.games.find((g) => g.id == args.id);
    },
    authors(_, args) {
      return db.authors.find((r) => r.id == args.id);
    },
    author(_, args) {
      return db.authors.find((a) => a.id == args.id);
    },
  },
  Game: {
    reviews(parent) {
      return db.reviews.filter((r) => r.game_id == parent.id);
    },
  },
  Author: {
    reviews(parent) {
      return db.reviews.filter((r) => r.author_id == parent.id);
    },
  },
  Review: {
    author(parent) {
      return db.authors.find((a) => a.id == parent.author_id);
    },
    game(parent) {
      return db.games.find((g) => g.id == parent.game_id);
    },
  },
  Mutation: {
    deleteGame(_, args) {
      return db.games.filter((g) => g.id != args.id);
    },
    addGame(_, args) {
      const game = { ...args.game, id: db.games.length + 1 };
      db.games.push(game);
      return game;
    },
    updateGame(_, args) {
      db.games.forEach((g, i) => {
        if (g.id == args.id) {
          db.games[i] = { ...g, ...args.game };
        }
      });
      return db.games.find(g => g.id == args.id)
    },
  },
};

const server = new ApolloServer({
  typeDefs,
  resolvers,
});

const { url } = await startStandaloneServer(server, {
  listen: {
    port: 4000,
  },
});

console.log("Server is running on port: 4000");
