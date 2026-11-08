const fs = require("fs");
const path = require("path");

const src = path.resolve(__dirname, "..", "..", "roster_and_weekend", "public", "roster", "index.html");
const dest = path.resolve(__dirname, "..", "..", "roster_and_weekend", "www", "roster.html");

fs.copyFileSync(src, dest);
console.log(`Copied ${src} -> ${dest}`);
