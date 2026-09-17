// Zet de ECHTE onboarding.js en de echte stijl van app.html naast de preview,
// zodat je bekijkt wat er verscheept wordt en niet een kopie die afdrijft.
// Draaien: node tests/onboarding-preview/build.js
const fs = require("fs");
const path = require("path");
const ROOT = path.join(__dirname, "..", "..");
fs.copyFileSync(path.join(ROOT, "frontend", "onboarding.js"), path.join(__dirname, "onboarding.js"));
const app = fs.readFileSync(path.join(ROOT, "frontend", "app.html"), "utf8");
const css = app.slice(app.indexOf("<style>") + 7, app.indexOf("</style>"));
fs.writeFileSync(path.join(__dirname, "app.css"), css);
console.log("preview gebouwd:", css.length, "tekens stijl");
