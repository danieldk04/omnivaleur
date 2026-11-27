/* Kenmerken uit de titel en omschrijving halen: doelgroep, categorie, kleur, maat.
 *
 * 27-11-2026 (Daniel): "de categorie, kleur en maat uit de titel en omschrijving
 * herkennen en alvast invullen, zodat het sneller gaat."
 *
 * Eén regel gaat voor alles: liever LEEG dan fout. Elke functie geeft alleen een
 * waarde terug als de tekst het ondubbelzinnig zegt. Zegt de tekst twee
 * verschillende dingen (twee kleuren, jas én trui, twee maten), dan is het
 * antwoord null en blijft het veld voor de verkoper. Zo vult dit nooit iets in
 * wat de tekst niet zegt.
 *
 * Alles is een pure functie van tekst naar waarde, zodat tests/kenmerken-uit-tekst-test.js
 * hem zonder browser kan draaien. De koppeling met het formulier staat in app.html.
 */
(function (root) {
  "use strict";

  const laag = (s) => String(s || "").toLowerCase().replace(/[’`´]/g, "'");

  // Merknamen waar een kleur- of kledingwoord in zit: die zijn geen kleur of soort.
  const MERK_STRIP = new RegExp([
    "red wing", "black diamond", "white stuff", "black yak", "blue harbour", "green label",
    "pink soda", "yellow submarine", "orange tab", "old navy", "black rock", "white mountaineering",
    "jack (?:&|and|en)? ?jones", "jack wolfskin", "jack daniel'?s", "jack & jones",
    "mint condition", "mint staat", "rose gold", "roségoud", "rosegoud", "off[- ]white",
    "top (?:condition|quality|staat|kwaliteit|merk|brand|seller)",
  ].join("|"), "g");

  function schoon(tekst) {
    return laag(tekst).replace(MERK_STRIP, " ");
  }

  // ---- doelgroep ----------------------------------------------------------------
  function doelgroep(tekst) {
    const t = schoon(tekst);
    const kind = /\b(kids?|kinder(?:en|kleding)?|boys?|girls?|jongens|meisjes|baby|peuter|junior|tiener)\b/.test(t);
    if (kind) return null;
    const heren = /\b(men|mens|men's|heren|herenkleding|male)\b/.test(t);
    const dames = /\b(women|womens|women's|ladies|lady|dames|damesmode|female)\b/.test(t);
    if (heren === dames) return null;
    return heren ? "heren" : "dames";
  }

  // ---- categorie ----------------------------------------------------------------
  const SPORT = /\b(jersey|voetbal|football|soccer|wieler|cycling|running|hardloop|sportshirt|trainingspak|tracksuit|ski|snowboard|yoga|gym)\w*/;

  // Volgorde is belangrijk: wat een ander woord bevat gaat eerst en wordt uit de
  // tekst gehaald, zodat "denim jacket" geen jeans is en "t-shirt" geen shirt.
  const SOORTEN = [
    ["jassen", /(?:denim|jeans|spijker)[- ]?(?:jackets?|jacks?|jas(?:sen)?)\b/g],
    ["jassen", /\b(?:fleece[- ]?)?(?:jackets?|jacks?|jas|jassen|jasje|fleecejas|fleecejack|coats?|parka|puffer|bomber|windbreaker|anorak|trenchcoat|windjack|regenjas|winterjas|zomerjas)\b/g],
    ["hoodies", /\b(?:hoodie|hoody|hooded sweat|sweatshirt)s?\b/g],
    ["truien", /\b(?:sweaters?|jumpers?|trui|truien|cardigans?|pullover|knitwear|knit|(?:half|quarter|kwart|halve)[- ]?zip|turtleneck|coltrui|crewneck|crew neck)\b/g],
    ["jeans", /\b(?:jeans|spijkerbroek)\b/g],
    ["shorts", /\b(?:shorts|korte broek|zwembroek)\b/g],
    ["broek", /\b(?:chinos?|trousers?|pants|broek|cargo|joggingbroek|sweatpants|joggers?)\b/g],
    ["polo", /\b(?:polo(?: shirt)?|polo's)\b/g],
    ["tshirt", /\b(?:t-?shirts?|tee|tees)\b/g],
    ["blouse", /\b(?:blouses?|tuniek|tunic)\b/g],
    ["overhemd", /\b(?:overhemden?|dress shirt)\b|(?<![a-z-])shirts?\b/g],
    ["top", /\b(?:tops?|topje)\b/g],
    ["jurk", /\b(?:dress|dresses|jurk|jurkje)\b/g],
    ["rok", /\b(?:skirts?|rok|rokje)\b/g],
  ];

  const SLEUTEL = {
    heren: { jassen: "heren jassen", hoodies: "heren hoodies", truien: "heren truien",
      jeans: "heren jeans", broek: "heren chinos", shorts: "heren shorts", polo: "heren polo's",
      tshirt: "heren t-shirts", overhemd: "heren overhemden" },
    dames: { jassen: "jassen", hoodies: "hoodies", truien: "truien", jeans: "jeans",
      broek: "broeken", shorts: "shorts", tshirt: "tops", top: "tops", blouse: "blouses",
      overhemd: "blouses", jurk: "jurken casual", rok: "rokken" },
  };

  // Alleen de TITEL: een omschrijving noemt al snel meer soorten ("mooi met een
  // jeans of chino") en dan wint de verkeerde.
  function categorie(titel, groep, beschikbaar) {
    if (groep !== "heren" && groep !== "dames") return null;
    let t = schoon(titel);
    if (SPORT.test(t)) return null;
    const gevonden = new Set();
    for (const [soort, re] of SOORTEN) {
      re.lastIndex = 0;
      if (re.test(t)) {
        gevonden.add(soort);
        re.lastIndex = 0;
        t = t.replace(re, " ");
      }
    }
    if (gevonden.size !== 1) return null;
    const key = SLEUTEL[groep][[...gevonden][0]];
    if (!key) return null;
    if (beschikbaar && !beschikbaar.includes(key)) return null;
    return key;
  }

  // ---- kleur --------------------------------------------------------------------
  const KLEUREN = [
    ["Navy", /\b(?:navy(?: blue)?|marine(?:blauw)?)\b/g],
    ["Light blue", /\b(?:light[- ]?blue|licht ?blauw)\w*\b/g],
    ["Dark green", /\b(?:dark[- ]?green|donker ?groen)\w*\b/g],
    ["Black", /\b(?:black|zwart)(?:e|en)?\b/g],
    ["Grey", /\b(?:grey|gray|grijs|grijze)\b/g],
    ["White", /\b(?:white|wit|witte)\b/g],
    ["Cream", /\b(?:cream|cr[eè]me|ecru)\b/g],
    ["Beige", /\bbeige\b/g],
    ["Orange", /\b(?:orange|oranje)\b/g],
    ["Red", /\b(?:red|rood|rode)\b/g],
    ["Burgundy", /\b(?:burgundy|bordeaux(?:rood)?)\b/g],
    ["Pink", /\b(?:pink|roze)\b/g],
    ["Purple", /\b(?:purple|paars|paarse)\b/g],
    ["Lilac", /\b(?:lilac|lila)\b/g],
    ["Blue", /\b(?:blue|blauw|blauwe)\b/g],
    ["Turquoise", /\bturquoise\b/g],
    ["Green", /\b(?:green|groen|groene)\b/g],
    ["Khaki", /\bkhaki\b/g],
    ["Brown", /\b(?:brown|bruin|bruine)\b/g],
    ["Mustard", /\b(?:mustard|mosterd\w*)\b/g],
    ["Yellow", /\b(?:yellow|geel|gele)\b/g],
    ["Silver", /\b(?:silver|zilver\w*)\b/g],
    ["Gold", /\b(?:gold|goud\w*)\b/g],
  ];

  function kleurIn(tekst) {
    let t = schoon(tekst);
    const g = new Set();
    for (const [naam, re] of KLEUREN) {
      re.lastIndex = 0;
      if (re.test(t)) { g.add(naam); re.lastIndex = 0; t = t.replace(re, " "); }
    }
    return g;
  }

  // Alleen de titel, en alleen als er precies één kleur in staat.
  function kleur(titel, beschikbaar) {
    const g = kleurIn(titel);
    if (g.size !== 1) return null;
    const naam = [...g][0];
    if (beschikbaar && !beschikbaar.includes(naam)) return null;
    return naam;
  }

  // ---- maat ---------------------------------------------------------------------
  const LETTER = "XXS|XS|S|M|L|XL|XXL|XXXL|[2-5]XL";
  const norm = (m) => (m === "XXXL" ? "3XL" : m);

  function maten(tekst, mag) {
    const t = String(tekst || "").replace(/[’`´]/g, "'");
    const g = new Set();
    let m;
    // "size M", "maat XL"
    const a = new RegExp(`(?<![A-Za-z])(?:size|maat|sz)\\.?\\s*[:=]?\\s*(${LETTER})(?![A-Za-z0-9])`, "gi");
    while ((m = a.exec(t))) g.add(norm(m[1].toUpperCase()));
    // "size M of L", "maat S/M", "size M - L": een keuze of reeks is geen maat.
    const reeks = new RegExp(`(?<![A-Za-z])(?:size|maat|sz)\\.?\\s*[:=]?\\s*(?:${LETTER})\\s*(?:of|or|en|and|/|-|–|t/m|to)\\s*(${LETTER})(?![A-Za-z0-9])`, "gi");
    while ((m = reeks.exec(t))) g.add(norm(m[1].toUpperCase()));
    // "Men M", "Dames XL" (maat in hoofdletters, anders is het een gewoon woord)
    const b = new RegExp(`(?<![A-Za-z])(?:men|mens|women|womens|heren|dames|unisex)\\s+(?:size\\s+|maat\\s+)?(${LETTER})(?![A-Za-z0-9])`, "gi");
    while ((m = b.exec(t))) { if (m[1] === m[1].toUpperCase()) g.add(norm(m[1])); }
    // "... - M - ...", "(L)", "| XL |": een los hoofdletterwoord tussen scheidingstekens
    const c = new RegExp(`(?:^|[-–—|,(\\[]\\s*)(${LETTER})\\s*(?=[-–—|,)\\]]|$)`, "g");
    while ((m = c.exec(t))) g.add(norm(m[1]));
    // "size 42", "maat 42", "EU 42"
    const d = /(?<![A-Za-z])(?:size|maat|sz|eu)\.?\s*[:=]?\s*(\d{2})(?![\d,.])/gi;
    while ((m = d.exec(t))) g.add(m[1]);
    // "W32 L34", "W32"
    const e = /(?<![A-Za-z])W\s?(2[4-9]|3\d|4[0-6])(?![\d])/g;
    while ((m = e.exec(t))) g.add("W" + m[1]);
    return [...g].filter((x) => !mag || mag.includes(x));
  }

  // Titel eerst; staat de maat daar niet, dan de omschrijving. Twee verschillende
  // maten, of titel en omschrijving die elkaar tegenspreken: null.
  function maat(titel, omschrijving, beschikbaar) {
    const t = maten(titel, null);
    const o = maten(omschrijving, null);
    let kies;
    if (t.length) {
      if (t.length > 1) return null;
      if (o.length && !(o.length === 1 && o[0] === t[0])) {
        // Omschrijving noemt iets anders: alleen laten staan als het duidelijk een reeks is.
        return null;
      }
      kies = t[0];
    } else {
      if (o.length !== 1) return null;
      kies = o[0];
    }
    if (beschikbaar && !beschikbaar.includes(kies)) return null;
    return kies;
  }

  const api = { doelgroep, categorie, kleur, maat, maten, kleurIn };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.KenmerkenUitTekst = api;
})(typeof window !== "undefined" ? window : globalThis);
