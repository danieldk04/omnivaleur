// Content script for vinted.com/items/new — uses the shared CL engine.
(async () => {
  const PLATFORM = "vinted";

  // Maps source-platform condition values (English keys, Dutch values) → Vinted English labels.
  // Marktplaats scale: zo goed als nieuw > goed > redelijk > beschadigd
  // Vinted scale: New with tags > New without tags > Very good > Good > Satisfactory
  const CONDITION_MAP = {
    // Dashboard condition keys (see app.html #f-condition)
    "new_with_tags": "New with tags",
    "new": "New without tags",   // dashboard "New (without tags)" — NOT new-with-tags
    "good": "Very good",
    "fair": "Good",
    "poor": "Satisfactory",
    // Dutch Marktplaats condition labels
    "nieuw met label":   "New with tags",
    "nieuw met labels":  "New with tags",
    "nieuw zonder label":"New without tags",
    "nieuw zonder labels":"New without tags",
    "zo goed als nieuw": "Very good",
    "zeer goed":         "Very good",
    "goed":              "Good",
    "lichte gebruikssporen": "Good",
    "gedragen":          "Good",
    "redelijk":          "Satisfactory",
    "gebruikt":          "Satisfactory",
    "matig":             "Satisfactory",
    "beschadigd":        "Satisfactory",
    // Vinted English pass-through
    "new with tags":    "New with tags",
    "new without tags": "New without tags",
    "very good":        "Very good",
    "satisfactory":     "Satisfactory",
  };

  // Dutch → Vinted English colour names.
  const COLOUR_MAP = {
    "zwart":        "Black",
    "grijs":        "Grey",
    "gray":         "Grey",   // US spelling — Vinted's own option is "Grey"
    "lichtgrijs":   "Light grey",
    "light grey":   "Light grey",
    "light gray":   "Light grey",
    "donkergrijs":  "Dark grey",
    "dark grey":    "Dark grey",
    "dark gray":    "Dark grey",
    "wit":          "White",
    "crème":        "Cream",
    "creme":        "Cream",
    "beige":        "Beige",
    "abrikoos":     "Apricot",
    "oranje":       "Orange",
    "koraal":       "Coral",
    "koraalrood":   "Coral",
    "rood":         "Red",
    "bordeaux":     "Burgundy",
    "wijnrood":     "Burgundy",
    "roze":         "Pink",
    "rose":         "Rose",
    "paars":        "Purple",
    "lila":         "Lilac",
    "lichtblauw":   "Light blue",
    "blauw":        "Blue",
    "marine":       "Navy",
    "marineblauw":  "Navy",
    "donkerblauw":  "Navy",
    "turkoois":     "Turquoise",
    "turquoise":    "Turquoise",
    "mintgroen":    "Mint",
    "mint":         "Mint",
    "groen":        "Green",
    "donkergroen":  "Dark green",
    "khaki":        "Khaki",
    "bruin":        "Brown",
    "mosterd":      "Mustard",
    "geel":         "Yellow",
    "zilver":       "Silver",
    "goud":         "Gold",
    "multi":        "Multi",
    "veelkleurig":  "Multi",
    "transparant":  "Clear",
    // English passthrough (dashboard sends English for many items) → canonical
    // Vinted label, so casing/normalisation is deterministic.
    "black":        "Black",
    "grey":         "Grey",
    "white":        "White",
    "cream":        "Cream",
    "apricot":      "Apricot",
    "orange":       "Orange",
    "coral":        "Coral",
    "red":          "Red",
    "burgundy":     "Burgundy",
    "pink":         "Pink",
    "rose":         "Rose",
    "purple":       "Purple",
    "lilac":        "Lilac",
    "blue":         "Blue",
    "navy":         "Navy",
    "turquoise":    "Turquoise",
    "mint":         "Mint",
    "green":        "Green",
    "yellow":       "Yellow",
    "mustard":      "Mustard",
    "brown":        "Brown",
    "silver":       "Silver",
    "gold":         "Gold",
    "multicolour":  "Multi",
    "multicolor":   "Multi",
    "clear":        "Clear",
  };

  // Dutch → Vinted English material names.
  const MATERIAL_MAP = {
    "wol":           "Wool",
    "katoen":        "Cotton",
    "zijde":         "Silk",
    "linnen":        "Linen",
    "polyester":     "Polyester",
    "nylon":         "Nylon",
    "acryl":         "Acrylic",
    "viscose":       "Viscose",
    "elastaan":      "Elastane",
    "spandex":       "Spandex",
    "leer":          "Leather",
    "leder":         "Leather",
    "kunstleer":     "Faux leather",
    "suède":         "Suede",
    "suede":         "Suede",
    "velvet":        "Velvet",
    "fluweel":       "Velvet",
    "satijn":        "Satin",
    "denim":         "Denim",
    "spijkerstof":   "Denim",
    "canvas":        "Canvas",
    "ribfluweel":    "Corduroy",
    "corduroy":      "Corduroy",
    "jersey":        "Jersey",
    "fleece":        "Fleece",
    "kasjmier":      "Cashmere",
    "mohair":        "Mohair",
    "angora":        "Angora",
    "bamboe":        "Bamboo",
    "modal":         "Modal",
    "lyocell":       "Lyocell",
    "tencel":        "Tencel",
    "ramee":         "Ramie",
    "hennep":        "Hemp",
    "jute":          "Jute",
    "rubber":        "Rubber",
    "latex":         "Latex",
    "pvc":           "PVC",
    // English pass-through (Vinted labels)
    "wool":          "Wool",
    "cotton":        "Cotton",
    "silk":          "Silk",
    "linen":         "Linen",
    "leather":       "Leather",
    "suede":         "Suede",
    "cashmere":      "Cashmere",
    "denim":         "Denim",
    "polyester":     "Polyester",
    "nylon":         "Nylon",
    "acrylic":       "Acrylic",
    "viscose":       "Viscose",
    "elastane":      "Elastane",
    "fleece":        "Fleece",
    "velvet":        "Velvet",
    "satin":         "Satin",
    "canvas":        "Canvas",
    "corduroy":      "Corduroy",
    "jersey":        "Jersey",
    "mohair":        "Mohair",
    "angora":        "Angora",
    "bamboo":        "Bamboo",
    "modal":         "Modal",
    "lyocell":       "Lyocell",
    "tencel":        "Tencel",
    "hemp":          "Hemp",
  };

  // Dutch → English category hints. Vinted's UI is English; we use these terms to
  // match against the "Suggested" options Vinted generates from the title/description.
  const CAT_HINTS = {
    // Deze termen zijn de ECHTE bladnamen uit Vinted's eigen categoriekiezer
    // (live nagelopen op vinted.nl, augustus 2026), niet zelfbedachte woorden.
    // Dat is het verschil tussen een wielrenshirt bij "Activewear > Team shirts
    // & jerseys" en bij "Sports > Cycling" — dat laatste is fietsMATERIAAL.
    // Sportkleding zit bij Vinted ALTIJD onder "Activewear"; daarom staat die
    // term overal voorop: elke passende hint telt apart mee in de score, dus
    // "activewear" + "shorts" wint van een gewone broek-categorie.
    //
    // Heren > Clothing:  Jeans · Outerwear · Tops & t-shirts · Suits & blazers ·
    //   Jumpers & sweaters · Trousers · Shorts · Socks & underwear · Sleepwear ·
    //   Swimwear · Activewear · Other clothing
    // Activewear (heren): Outerwear · Tracksuits · Trousers · Shorts ·
    //   Tops & t-shirts · Team shirts & jerseys · Pullovers & sweaters ·
    //   Sports accessories · Other activewear
    // Activewear (dames): idem + Dresses · Skirts · Hoodies & sweatshirts · Sports bras
    // ── Dames ──────────────────────────────────────────────────────
    "jeans":              ["jeans"],
    "broeken":            ["trousers & leggings", "trousers"],
    "shorts":             ["shorts & cropped trousers", "shorts"],
    "rokken":             ["skirts"],
    "jurken casual":      ["dresses"],
    "jurken feest":       ["dresses"],
    "blouses":            ["tops & t-shirts", "blouses", "shirts"],
    "tops":               ["tops & t-shirts"],
    "truien":             ["jumpers & sweaters", "cardigans"],
    "hoodies":            ["hoodies & sweatshirts", "jumpers & sweaters"],
    "jassen":             ["outerwear", "coats", "jackets"],
    "sport bh":           ["activewear", "sports bras"],
    "sportleggings":      ["activewear", "trousers"],
    "sportbroeken":       ["activewear", "shorts"],
    "sport tops":         ["activewear", "tops & t-shirts"],
    "sportjassen":        ["activewear", "outerwear"],
    "trainingspakken":    ["activewear", "tracksuits"],
    "hardloopkleding":    ["activewear", "tops & t-shirts", "shorts"],
    "wielrenkleding":     ["activewear", "team shirts & jerseys", "other activewear"],
    "voetbalkleding":     ["activewear", "team shirts & jerseys"],
    "yogakleding":        ["activewear", "trousers", "other activewear"],
    "yoga kleding":       ["activewear", "trousers", "other activewear"],
    "gymkleding":         ["activewear", "tops & t-shirts", "other activewear"],
    "skikleding":         ["activewear", "outerwear", "other activewear"],
    "sportkleding":       ["activewear", "other activewear"],
    "zwemkleding":        ["swimwear"],
    "ondergoed":          ["lingerie & nightwear", "socks & underwear"],
    "sneakers dames":     ["sneakers", "trainers", "sports shoes"],
    "schoenen dames":     ["shoes", "loafers", "flats", "boat shoes"],
    "hakken":             ["heels", "pumps", "high heels"],
    "laarzen dames":      ["boots", "ankle boots", "knee-high boots"],
    "sandalen":           ["sandals", "flip flops", "slippers"],
    "accessoires dames":  ["accessories", "bags", "scarves", "jewellery"],
    // ── Heren ──────────────────────────────────────────────────────
    "heren jeans":            ["jeans"],
    "heren chinos":           ["trousers", "chinos"],
    "heren shorts":           ["shorts"],
    "heren t-shirts":         ["tops & t-shirts", "t-shirts"],
    "heren polo's":           ["tops & t-shirts", "polo shirts"],
    "heren overhemden":       ["tops & t-shirts", "shirts"],
    "heren truien":           ["jumpers & sweaters"],
    "heren hoodies":          ["jumpers & sweaters", "hoodies & sweatshirts"],
    "heren jassen":           ["outerwear", "coats", "jackets"],
    "heren pakken":           ["suits & blazers"],
    "heren sport tops":       ["activewear", "tops & t-shirts"],
    "heren sportbroeken":     ["activewear", "shorts", "trousers"],
    "heren sportjassen":      ["activewear", "outerwear"],
    "heren trainingspakken":  ["activewear", "tracksuits"],
    "heren hardloopkleding":  ["activewear", "tops & t-shirts", "shorts"],
    "heren wielrenkleding":   ["activewear", "team shirts & jerseys", "other activewear"],
    "heren voetbalkleding":   ["activewear", "team shirts & jerseys"],
    "heren gymkleding":       ["activewear", "tops & t-shirts", "other activewear"],
    "heren skikleding":       ["activewear", "outerwear", "other activewear"],
    "heren sportkleding":     ["activewear", "other activewear"],
    "heren zwembroeken":      ["swimwear"],
    "heren ondergoed":        ["socks & underwear"],
    "heren sneakers":         ["sneakers", "trainers", "sports shoes"],
    "heren schoenen":         ["shoes", "loafers", "boat shoes"],
    "heren formele schoenen": ["formal shoes", "dress shoes", "oxford shoes"],
    "heren laarzen":          ["boots", "ankle boots"],
    "heren accessoires":      ["accessories", "belts", "scarves", "hats"],
    // ── Kinderen ───────────────────────────────────────────────────
    "babykleding":            ["baby", "baby clothing", "newborn"],
    "peuterkleding":          ["toddler", "kids clothing"],
    "jongens kleding":        ["boys clothing"],
    "meisjes kleding":        ["girls clothing"],
    "tieners jongens":        ["boys clothing"],
    "tieners meisjes":        ["girls clothing"],
    "kinderen sportkleding":  ["activewear", "other activewear"],
    "kinderen wielrenkleding":["activewear", "team shirts & jerseys", "other activewear"],
    "kinderen voetbalkleding":["activewear", "team shirts & jerseys"],
    "kinderen zwemkleding":   ["swimwear"],
    "kinderen schoenen":      ["shoes", "kids shoes"],
    "kinderen accessoires":   ["accessories"],
    // ── Unisex ─────────────────────────────────────────────────────
    // Vinted heeft geen eigen carnavalstak; "Other clothing" is de bladnaam waar
    // verkleedkleding en klederdracht daar terechtkomen.
    "verkleedkleding":     ["other clothing"],
    "heren verkleedkleding": ["other clothing"],
    "unisex verkleedkleding": ["other clothing"],
    "unisex truien":       ["jumpers & sweaters", "hoodies & sweatshirts"],
    "unisex jassen":       ["outerwear", "jackets", "coats"],
    "unisex sportkleding": ["activewear", "other activewear"],
    "unisex wielrenkleding": ["activewear", "team shirts & jerseys", "other activewear"],
    "unisex trainingspakken": ["activewear", "tracksuits"],
    "unisex hardloopkleding": ["activewear", "tops & t-shirts", "shorts"],
    "unisex schoenen":     ["shoes", "sneakers", "trainers"],
    "unisex accessoires":  ["accessories", "scarves", "hats"],
    // ── English dashboard category keys (the dashboard UI is English, so item.category
    //    arrives as e.g. "shoes"/"trainers", not the Dutch keys above). Sneakers/
    //    trainers lead the generic "shoes" list so a plain shoe lands there rather
    //    than in a niche sport category. The score() niche-penalty backs this up.
    "shoes":               ["sneakers", "trainers", "shoes", "loafers", "boat shoes"],
    "sneakers":            ["sneakers", "trainers", "sports shoes"],
    "trainers":            ["trainers", "sneakers", "sports shoes"],
    "boots":               ["boots", "ankle boots", "chelsea boots"],
    "heels":               ["heels", "pumps", "high heels"],
    "sandals":             ["sandals", "flip flops", "slippers"],
    "loafers":             ["loafers", "boat shoes", "moccasins"],
    // ── Legacy keys (backwards compat for existing saved items) ────
    // LET OP: hier mag alleen een sleutel staan die NIET meer in de
    // dashboard-keuzelijst voorkomt. JavaScript laat bij een dubbele sleutel
    // stilzwijgend de laatste winnen, en dit blok staat onderaan — dus een
    // sleutel die hierboven al bestaat wordt hier overschreven door de oude,
    // grovere hint. Dat was tot 27-08-2026 het geval voor sportkleding,
    // ondergoed en pakken (dames en heren): "ondergoed" kreeg ["underwear"]
    // in plaats van ["lingerie & nightwear", "socks & underwear"]. Die vijf
    // regels zijn weggehaald; test_vinted_categories bewaakt het nu.
    "schoenen":            ["sneakers", "trainers", "shoes", "loafers", "boots"],
    "truien / vesten":     ["jumpers", "cardigans", "knitwear"],
    "heren truien / vesten": ["jumpers", "sweaters", "cardigans", "knitwear"],
    "heren t-shirts / polo": ["t-shirts", "polo shirts"],
    "jassen | winter":     ["coats", "winter coats", "jackets"],
    "blouses en tunieken": ["blouses", "tunics", "shirts"],
    "polo's":              ["polo shirts", "polos"],
    "overhemden":          ["shirts"],
    "leggings":            ["leggings"],
    "badkleding":          ["swimwear", "swimsuits"],
    "heren broeken":       ["trousers", "pants", "chinos"],
    // ── Non-clothing (games, consoles, electronics) ───────────────
    // Vinted has "Video games & consoles" and (in some markets) "Electronics".
    // If a market lacks these leaves no row matches and fillCategoryVinted
    // returns false — safe (the user picks manually), never miscategorised.
    // ── Games (software) ──
    "games playstation 5":                ["playstation 5 games", "playstation 5", "video games", "games"],
    "games playstation 4":                ["playstation 4 games", "playstation 4", "video games", "games"],
    "games playstation 3":                ["playstation 3 games", "playstation 3", "video games", "games"],
    "games playstation 2":                ["playstation 2 games", "playstation 2", "video games", "games"],
    "games playstation 1":                ["playstation 1 games", "playstation 1", "video games", "games"],
    "games psp":                          ["psp games", "psp", "video games", "games"],
    "games ps vita":                      ["ps vita games", "ps vita", "video games", "games"],
    "games nintendo switch":              ["nintendo switch games", "nintendo switch", "video games", "games"],
    "games nintendo wii u":               ["wii u games", "wii u", "video games", "games"],
    "games nintendo wii":                 ["wii games", "wii", "video games", "games"],
    "games nintendo 3ds":                 ["3ds games", "3ds", "video games", "games"],
    "games nintendo ds":                  ["nintendo ds games", "nintendo ds", "video games", "games"],
    "games gamecube":                     ["gamecube games", "gamecube", "video games", "games"],
    "games nintendo 64":                  ["nintendo 64 games", "nintendo 64", "video games", "games"],
    "games snes":                         ["snes games", "snes", "video games", "games"],
    "games nes":                          ["nes games", "nes", "video games", "games"],
    "games gameboy":                      ["game boy games", "game boy", "video games", "games"],
    "games xbox series":                  ["xbox series games", "xbox series", "video games", "games"],
    "games xbox one":                     ["xbox one games", "xbox one", "video games", "games"],
    "games xbox 360":                     ["xbox 360 games", "xbox 360", "video games", "games"],
    "games xbox original":                ["xbox games", "xbox", "video games", "games"],
    "games pc":                           ["pc games", "pc", "video games", "games"],
    "games sega":                         ["sega games", "sega", "video games", "games"],
    "games atari":                        ["atari games", "atari", "video games", "games"],
    "games overige":                      ["video games", "games"],
    // ── Game consoles (hardware) ──
    "games console playstation 5":               ["playstation 5", "consoles", "game consoles"],
    "games console playstation 4":               ["playstation 4", "consoles", "game consoles"],
    "games console playstation 3":               ["playstation 3", "consoles", "game consoles"],
    "games console playstation 2":               ["playstation 2", "consoles", "game consoles"],
    "games console playstation 1":               ["playstation 1", "consoles", "game consoles"],
    "games console ps vita":                     ["ps vita", "consoles", "game consoles"],
    "games console psp":                         ["psp", "consoles", "game consoles"],
    "games console nintendo switch":             ["nintendo switch", "consoles", "game consoles"],
    "games console nintendo switch lite":        ["switch lite", "consoles", "game consoles"],
    "games console nintendo wii u":              ["wii u", "consoles", "game consoles"],
    "games console nintendo wii":                ["wii", "consoles", "game consoles"],
    "games console nintendo 3ds":                ["3ds", "consoles", "game consoles"],
    "games console nintendo ds":                 ["nintendo ds", "consoles", "game consoles"],
    "games console gamecube":                    ["gamecube", "consoles", "game consoles"],
    "games console nintendo 64":                 ["nintendo 64", "consoles", "game consoles"],
    "games console snes":                        ["snes", "consoles", "game consoles"],
    "games console nes":                         ["nes", "consoles", "game consoles"],
    "games console gameboy":                     ["game boy", "consoles", "game consoles"],
    "games console xbox series":                 ["xbox series", "consoles", "game consoles"],
    "games console xbox one":                    ["xbox one", "consoles", "game consoles"],
    "games console xbox 360":                    ["xbox 360", "consoles", "game consoles"],
    "games console xbox original":               ["xbox", "consoles", "game consoles"],
    "games console sega":                        ["sega", "consoles", "game consoles"],
    "games console atari":                       ["atari", "consoles", "game consoles"],
    "games console overige":                     ["consoles", "game consoles"],
    // ── Electronics ─ phones ──
    "electronics telefoon apple iphone":         ["iphone", "apple", "smartphones", "phones", "mobile phones"],
    "electronics telefoon samsung":              ["samsung", "smartphones", "phones", "mobile phones"],
    "electronics telefoon huawei":               ["huawei", "smartphones", "phones", "mobile phones"],
    "electronics telefoon sony":                 ["sony", "smartphones", "phones", "mobile phones"],
    "electronics telefoon nokia":                ["nokia", "smartphones", "phones", "mobile phones"],
    "electronics telefoon lg":                   ["lg", "smartphones", "phones", "mobile phones"],
    "electronics telefoon motorola":             ["motorola", "smartphones", "phones", "mobile phones"],
    "electronics telefoon htc":                  ["htc", "smartphones", "phones", "mobile phones"],
    "electronics telefoon blackberry":           ["blackberry", "smartphones", "phones", "mobile phones"],
    "electronics telefoon overige":              ["smartphones", "phones", "mobile phones"],
    // ── Audio, tv en foto ──
    "audio luidsprekers":                  ["speakers", "hi-fi", "audio"],
    "audio soundbars":                     ["soundbar", "speakers", "audio"],
    "audio koptelefoons":                  ["headphones", "audio"],
    "audio versterkers en receivers":      ["amplifier", "hi-fi", "audio"],
    "audio buizenversterkers":             ["amplifier", "hi-fi", "audio"],
    "audio tuners":                        ["tuner", "hi-fi", "audio"],
    "audio stereo sets":                   ["stereo", "hi-fi", "audio"],
    "audio home cinema sets":              ["home cinema", "speakers", "audio"],
    "audio platenspelers":                 ["turntable", "record player", "audio"],
    "audio cd spelers":                    ["cd player", "hi-fi", "audio"],
    "audio blu ray spelers":               ["blu-ray player", "dvd player"],
    "audio dvd spelers":                   ["dvd player"],
    "audio videospelers":                  ["vcr", "video player"],
    "audio cassettedecks":                 ["cassette deck", "tape deck", "audio"],
    "audio bandrecorders":                 ["reel to reel", "tape recorder", "audio"],
    "audio radio s":                       ["radio", "audio"],
    "audio walkmans en discmans":          ["walkman", "discman", "portable audio"],
    "audio mp3 spelers ipod":              ["ipod", "mp3 player"],
    "audio mp3 spelers overige":           ["mp3 player"],
    "audio mp4 spelers":                   ["mp4 player", "mp3 player"],
    "audio mp3 accessoires ipod":          ["ipod", "accessories"],
    "audio mp3 accessoires overige":       ["mp3 player", "accessories"],
    "audio mediaspelers":                  ["media player", "streaming"],
    "audio karaoke apparatuur":            ["karaoke", "audio"],
    "audio professionele audio en video":  ["pro audio", "audio"],
    "audio televisies":                    ["tv", "television"],
    "audio vintage televisies":            ["vintage tv", "television"],
    "audio televisiebeugels":              ["tv mount", "tv bracket"],
    "audio televisie accessoires":         ["tv accessories"],
    "audio afstandsbedieningen":           ["remote control"],
    "audio decoders en harddiskrecorders": ["decoder", "recorder"],
    "audio schotelantennes":               ["satellite dish", "antenna"],
    "audio audio en tv kabels":            ["cables", "audio"],
    "audio converters":                    ["converter", "adapter"],
    "audio opladers":                      ["charger"],
    "audio accu s en batterijen":          ["battery", "batteries"],
    "audio beamers":                       ["projector", "beamer"],
    "audio beamer accessoires":            ["projector", "accessories"],
    "audio projectieschermen":             ["projector screen"],
    "audio diaprojectors":                 ["slide projector", "projector"],
    "audio videobewaking":                 ["security camera", "camera"],
    "audio drones":                        ["drone", "camera"],
    "audio actiecamera s":                 ["action camera", "gopro", "camera"],
    "audio fotocamera s digitaal":         ["digital camera", "camera"],
    "audio fotocamera s analoog":          ["film camera", "analog camera", "camera"],
    "audio onderwatercamera s":            ["underwater camera", "camera"],
    "audio videocamera s digitaal":        ["camcorder", "video camera"],
    "audio videocamera s analoog":         ["camcorder", "video camera"],
    "audio lenzen en objectieven":         ["camera lens", "camera"],
    "audio filters":                       ["lens filter", "camera"],
    "audio flitsers":                      ["camera flash", "camera"],
    "audio statieven en balhoofden":       ["tripod", "camera"],
    "audio fototassen":                    ["camera bag", "bags"],
    "audio geheugenkaarten":               ["memory card", "sd card"],
    "audio fotografie accu s":             ["camera battery", "battery"],
    "audio fotostudio en toebehoren":      ["studio light", "photography"],
    "audio professionele fotoapparatuur":  ["photography", "camera"],
    "audio doka toebehoren":               ["darkroom", "photography"],
    "audio filmrollen":                    ["film roll", "35mm film"],
    "audio fotopapier":                    ["photo paper"],
    "audio fotolijsten":                   ["photo frame", "frames"],
    "audio digitale fotolijsten":          ["digital photo frame"],
    "audio fotoalbums en accessoires":     ["photo album"],
    "audio verrekijkers":                  ["binoculars"],
    "audio telescopen":                    ["telescope"],
    "audio microscopen":                   ["microscope"],
    "audio weerstations en barometers":    ["weather station", "barometer"],
    "audio overige audio tv en foto":      ["audio", "electronics"],
    // ── Sieraden, horloges en tassen ──────────────────────────────
    // These arrive from the dedicated "Jewellery, Watches & Bags" item type, so
    // the leaf is known exactly — no guessing from the title needed (that's what
    // ACCESSORY_TERMS below is for, and only for the coarse clothing "accessoires"
    // buckets). Vinted files these under Accessories per gender; the generic
    // fallbacks at the end of each list let score() land on whichever the market has.
    "sieraden horloges dames":    ["watches", "watch", "accessories"],
    "sieraden horloges heren":    ["watches", "watch", "accessories"],
    "sieraden horloges kinderen": ["watches", "watch", "accessories"],
    "sieraden horloges antiek":   ["watches", "watch", "accessories"],
    "sieraden smartwatch":        ["smartwatches", "watches", "watch"],
    "sieraden sporthorloge":      ["watches", "watch", "accessories"],
    "sieraden activity tracker":  ["smartwatches", "watches", "accessories"],
    "sieraden kettingen":         ["necklaces", "jewellery", "jewelry"],
    "sieraden kettinghangers":    ["necklaces", "pendants", "jewellery", "jewelry"],
    "sieraden armbanden":         ["bracelets", "jewellery", "jewelry"],
    "sieraden ringen":            ["rings", "jewellery", "jewelry"],
    "sieraden oorbellen":         ["earrings", "jewellery", "jewelry"],
    "sieraden bedels":            ["charms", "jewellery", "jewelry"],
    "sieraden broches":           ["brooches", "jewellery", "jewelry"],
    "sieraden enkelbandjes":      ["anklets", "bracelets", "jewellery", "jewelry"],
    "sieraden kindersieraden":    ["jewellery", "jewelry", "accessories"],
    "sieraden antiek":            ["jewellery", "jewelry", "accessories"],
    "sieraden damestassen":       ["handbags", "bags", "shoulder bags"],
    "sieraden schoudertassen":    ["shoulder bags", "handbags", "bags"],
    "sieraden rugtassen":         ["backpacks", "bags"],
    "sieraden reistassen":        ["travel bags", "weekend bags", "bags"],
    "sieraden sporttassen":       ["sports bags", "gym bags", "bags"],
    "sieraden koffers":           ["suitcases", "luggage", "travel bags", "bags"],
    "sieraden portemonnees":      ["wallets", "purses", "accessories"],
    "sieraden zonnebril dames":   ["sunglasses", "glasses", "accessories"],
    "sieraden zonnebril heren":   ["sunglasses", "glasses", "accessories"],

    // Wonen, antiek/kunst en muziek. Deze groepen kwamen in augustus 2026 in het
    // dashboard erbij, maar kregen hier nooit een bestemming — 137 categorieen
    // lang. Gevolg: de categoriestap vond niets, mislukte stil (step() logt en
    // gaat door) en de advertentie ging zonder categorie naar Vinted.
    //
    // Vinted is bewust GEEN kleding-only platform in dit project — zie
    // backend/services/platformregels.py: Home, Elektronica, Boeken & multimedia,
    // Hobby's & verzamelen en Sport horen er gewoon bij. Deze artikelen zijn dus
    // echt te plaatsen en horen een hint te hebben.
    //
    // Let op wat deze waarden ZIJN: zoekwoorden die in Vinted's eigen
    // categoriezoekvak worden getypt (zie typeSearch), geen vaste categorie-ID's.
    // Een gewoon Engels zelfstandig naamwoord is daarom de juiste waarde, en een
    // hint die niets vindt is niet erger dan de lege lijst van hiervoor.
    "wonen tuinmeubel accessoires":                        ["garden furniture accessories", "garden"],
    "wonen parasols":                                      ["parasol", "garden"],
    "wonen tuinstoelen":                                   ["garden chair", "garden furniture"],
    "wonen tuintafels":                                    ["garden table", "garden furniture"],
    "wonen tuinsets en loungesets":                        ["garden furniture set", "garden furniture"],
    "wonen tuinbanken":                                    ["garden bench", "garden furniture"],
    "wonen ligbedden":                                     ["sun lounger", "garden furniture"],
    "wonen bloembakken en plantenbakken":                  ["planter", "garden"],
    "wonen bloempotten":                                   ["flower pot", "garden"],
    "wonen buitenverlichting":                             ["outdoor lighting", "lighting"],
    "wonen vuurkorven":                                    ["fire pit", "garden"],
    "wonen terrasverwarmers":                              ["patio heater", "garden"],
    "wonen partytenten":                                   ["party tent", "garden"],
    "wonen overkappingen":                                 ["gazebo", "garden"],
    "wonen schaduwdoeken":                                 ["shade sail", "garden"],
    "wonen zonneschermen":                                 ["awning", "garden"],
    "wonen hangmatten":                                    ["hammock", "garden"],
    "wonen picknicktafels":                                ["picnic table", "garden furniture"],
    "wonen gordijnen en lamellen":                         ["curtains", "home textiles"],
    "wonen barkrukken":                                    ["bar stool", "furniture"],
    "wonen stoelen":                                       ["chair", "furniture"],
    "wonen krukjes":                                       ["stool", "furniture"],
    "wonen fauteuils":                                     ["armchair", "furniture"],
    "wonen eettafels":                                     ["dining table", "furniture"],
    "wonen salontafels":                                   ["coffee table", "furniture"],
    "wonen bijzettafels":                                  ["side table", "furniture"],
    "wonen tapijten en kleden":                            ["rug", "home textiles"],
    "wonen kussens":                                       ["cushion", "home textiles"],
    "wonen plaids en woondekens":                          ["blanket", "home textiles"],
    "wonen vachten":                                       ["sheepskin", "home textiles"],
    "wonen beddengoed":                                    ["bedspread", "home textiles"],
    "wonen vazen":                                         ["vase", "home decor"],
    "wonen spiegels":                                      ["mirror", "home decor"],
    "wonen wanddecoraties":                                ["wall decor", "home decor"],
    "wonen kunstplanten":                                  ["artificial plant", "home decor"],
    "wonen tafellampen":                                   ["table lamp", "lighting"],
    "wonen vloerlampen":                                   ["floor lamp", "lighting"],
    "wonen hanglampen":                                    ["pendant light", "lighting"],
    "wonen kandelaars en kaarsen":                         ["candle holder", "home decor"],
    "wonen tafelkleden":                                   ["tablecloth", "home textiles"],
    "wonen overige huis en inrichting":                    ["home decor", "home"],
    "wonen kerst":                                         ["christmas decoration", "home decor"],
    "antiek curiosa en brocante":                          ["collectables", "antiques"],
    "antiek glas en kristal":                              ["crystal glassware", "antiques"],
    "kunst schilderijen klassiek":                         ["classical painting", "art"],
    "antiek vazen":                                        ["antique vase", "antiques"],
    "antiek keramiek en aardewerk":                        ["ceramics pottery", "antiques"],
    "antiek overige antiek":                               ["antiques", "collectables"],
    "antiek woonaccessoires":                              ["home accessories", "antiques"],
    "antiek porselein":                                    ["porcelain", "antiques"],
    "antiek servies los":                                  ["tableware", "antiques"],
    "kunst beelden en houtsnijwerken":                     ["sculpture", "art"],
    "antiek meubels stoelen en banken":                    ["antique chair", "furniture"],
    "antiek lampen":                                       ["antique lamp", "lighting"],
    "kunst schilderijen modern":                           ["modern painting", "art"],
    "antiek wandborden en tegels":                         ["decorative tile", "antiques"],
    "kunst etsen en gravures":                             ["etching", "art"],
    "antiek koper en brons":                               ["brass bronze", "antiques"],
    "antiek bestek":                                       ["cutlery", "tableware"],
    "antiek boeken en bijbels":                            ["antique book", "books"],
    "antiek klokken":                                      ["antique clock", "antiques"],
    "antiek meubels kasten":                               ["antique cabinet", "furniture"],
    "antiek speelgoed":                                    ["antique toy", "toys"],
    "kunst niet westerse kunst":                           ["tribal art", "art"],
    "antiek schalen":                                      ["bowl", "tableware"],
    "antiek meubels tafels":                               ["antique table", "furniture"],
    "antiek gereedschap en instrumenten":                  ["antique tools", "antiques"],
    "kunst schilderijen abstract":                         ["abstract painting", "art"],
    "antiek religie":                                      ["religious antique", "antiques"],
    "kunst designobjecten":                                ["design object", "art"],
    "antiek emaille":                                      ["enamelware", "antiques"],
    "antiek goud en zilver":                               ["silverware", "antiques"],
    "kunst litho s en zeefdrukken":                        ["lithograph", "art"],
    "kunst tekeningen en foto s":                          ["drawing", "art"],
    "antiek keukenbenodigdheden":                          ["kitchenware", "antiques"],
    "antiek servies compleet":                             ["dinner service", "tableware"],
    "antiek kandelaars":                                   ["candlestick", "home decor"],
    "antiek spiegels":                                     ["antique mirror", "home decor"],
    "antiek tin":                                          ["pewter", "antiques"],
    "antiek kleden en textiel":                            ["antique textile", "home textiles"],
    "kunst overige kunst":                                 ["art"],
    "antiek kantoor en zakelijk":                          ["vintage office", "antiques"],
    "antiek schoolplaten":                                 ["school poster", "antiques"],
    "antiek kleding en accessoires":                       ["vintage clothing", "clothing"],
    "antiek naaimachines":                                 ["sewing machine", "antiques"],
    "antiek tv s en audio":                                ["vintage audio", "electronics"],
    "antiek meubels bedden":                               ["antique bed", "furniture"],
    "muziek accordeons":                                   ["accordion", "musical instrument"],
    "muziek behuizingen en koffers":                       ["instrument case", "music accessories"],
    "muziek blaasinstrumenten blokfluiten":                ["recorder flute", "wind instrument"],
    "muziek blaasinstrumenten didgeridoos":                ["didgeridoo", "wind instrument"],
    "muziek blaasinstrumenten dwarsfluiten en piccolo's":  ["flute", "wind instrument"],
    "muziek blaasinstrumenten hobo's":                     ["oboe", "wind instrument"],
    "muziek blaasinstrumenten hoorns":                     ["french horn", "brass instrument"],
    "muziek blaasinstrumenten klarinetten":                ["clarinet", "wind instrument"],
    "muziek blaasinstrumenten mondharmonica's":            ["harmonica", "wind instrument"],
    "muziek blaasinstrumenten overige":                    ["wind instrument", "musical instrument"],
    "muziek blaasinstrumenten saxofoons":                  ["saxophone", "wind instrument"],
    "muziek blaasinstrumenten trombones":                  ["trombone", "brass instrument"],
    "muziek blaasinstrumenten trompetten":                 ["trumpet", "brass instrument"],
    "muziek blaasinstrumenten tuba's":                     ["tuba", "brass instrument"],
    "muziek bladmuziek":                                   ["sheet music", "music"],
    "muziek dj-sets en draaitafels":                       ["turntable", "dj equipment"],
    "muziek draaiorgels":                                  ["barrel organ", "musical instrument"],
    "muziek drumcomputers":                                ["drum machine", "music equipment"],
    "muziek drumstellen en slagwerk":                      ["drum kit", "musical instrument"],
    "muziek effecten":                                     ["effects pedal", "music equipment"],
    "muziek instrumenten onderdelen":                      ["instrument parts", "music accessories"],
    "muziek instrumenten toebehoren":                      ["instrument accessories", "music accessories"],
    "muziek kabels en stekkers":                           ["audio cable", "music accessories"],
    "muziek keyboards":                                    ["keyboard", "musical instrument"],
    "muziek licht en laser":                               ["stage light", "music equipment"],
    "muziek mengpanelen":                                  ["mixer", "music equipment"],
    "muziek microfoons":                                   ["microphone", "music equipment"],
    "muziek midi-apparatuur":                              ["midi controller", "music equipment"],
    "muziek orgels":                                       ["organ", "keyboard instrument"],
    "muziek orkestbanden":                                 ["backing track", "music"],
    "muziek overige muziek en instrumenten":               ["musical instrument", "music"],
    "muziek percussie":                                    ["percussion", "musical instrument"],
    "muziek piano's":                                      ["piano", "keyboard instrument"],
    "muziek samplers":                                     ["sampler", "music equipment"],
    "muziek snaarinstrumenten banjo's":                    ["banjo", "string instrument"],
    "muziek snaarinstrumenten gitaren akoestisch":         ["acoustic guitar", "guitar"],
    "muziek snaarinstrumenten gitaren bas":                ["bass guitar", "guitar"],
    "muziek snaarinstrumenten gitaren elektrisch":         ["electric guitar", "guitar"],
    "muziek snaarinstrumenten harpen":                     ["harp", "string instrument"],
    "muziek snaarinstrumenten klavecimbels":               ["harpsichord", "keyboard instrument"],
    "muziek snaarinstrumenten mandolines":                 ["mandolin", "string instrument"],
    "muziek snaarinstrumenten overige":                    ["string instrument", "musical instrument"],
    "muziek soundmodules":                                 ["sound module", "music equipment"],
    "muziek standaards":                                   ["instrument stand", "music accessories"],
    "muziek strijkinstrumenten cello's":                   ["cello", "string instrument"],
    "muziek strijkinstrumenten contrabassen":              ["double bass", "string instrument"],
    "muziek strijkinstrumenten overige":                   ["string instrument", "musical instrument"],
    "muziek strijkinstrumenten violen en altviolen":       ["violin", "string instrument"],
    "muziek synthesizers":                                 ["synthesizer", "music equipment"],
    "muziek theaterbelichting":                            ["stage lighting", "music equipment"],
    "muziek versterkers bas en gitaar":                    ["guitar amplifier", "music equipment"],
    "muziek versterkers keyboard, monitor en pa":          ["pa amplifier", "music equipment"],
  };

  // Accessory nouns → the Vinted leaves they belong to. Used only when the
  // dashboard category is an "accessories" bucket (see fillCategoryVinted), where
  // the category itself is too coarse to pick a leaf. Ordered most-specific first;
  // the first regex that matches the title/description wins.
  const ACCESSORY_TERMS = [
    [/\b(horloge|horloges|watch|watches|smartwatch)\b/,            ["watches", "watch"]],
    [/\b(zonnebril|zonnebrillen|sunglasses)\b/,                    ["sunglasses", "glasses"]],
    [/\b(ketting|kettingen|armband|armbanden|ring|ringen|oorbel|oorbellen|sieraad|sieraden|jewellery|jewelry|necklace|bracelet|earrings)\b/,
                                                                   ["jewellery", "jewelry"]],
    [/\b(riem|riemen|belt|belts)\b/,                               ["belts", "belt"]],
    [/\b(sjaal|sjaals|shawl|scarf|scarves)\b/,                     ["scarves", "scarf"]],
    [/\b(muts|mutsen|pet|petten|cap|caps|hat|hats|beanie)\b/,      ["hats", "caps", "hats & caps"]],
    [/\b(handschoen|handschoenen|gloves)\b/,                       ["gloves"]],
    [/\b(portemonnee|portemonnees|wallet|wallets|purse)\b/,        ["wallets", "purses"]],
    [/\b(tas|tassen|handtas|schoudertas|rugzak|bag|bags|backpack)\b/, ["bags", "handbags", "backpacks"]],
  ];

  const { step, qs, sleep, waitUntil, waitForEl, fillInput, fillDescription, uploadPhotos, submitListing, clog }
    = window.CL;

  // ⚠ ALLE const/let van dit bestand horen hierboven de `await` hieronder te
  // staan. Dit bestand is één grote async functie: zodra hij bij `await getJob()`
  // wacht, is de rest van de regels nog niet uitgevoerd. Een const die verderop
  // staat bestaat op dat moment dus nog NIET, en elke functie die hem gebruikt
  // stopt met een harde fout op het moment dat hij aangeroepen wordt.
  //
  // Precies dat gebeurde bij de kleur: de kleurstap viel meteen om op zijn eigen
  // veldnaam en heeft nooit ook maar één klik gedaan — vandaar dat geen enkele
  // verbetering aan het aanklikken verschil maakte. Zet nieuwe waarden hier.
  const COLOUR_TRIGGER_SEL = 'input[data-testid="color-select-dropdown-input"]';
  const OTHER_TRIGGER_SEL = 'input[data-testid="category-material-multi-list-input"],'
    + 'input[data-testid="category-condition-single-list-input"],'
    + 'input[data-testid="brand-select-dropdown-input"],'
    + 'input[data-testid^="category-size"]';
  // Matching these by a loose "delete" substring would delete a photo instead of
  // the listing — verified live 2026-07. Always exclude them.
  const isPhotoDeleteTestid = (tid) => /media-select|grid-delete-button|image-wrapper/i.test(tid || "");
  const WARDROBE_PER_PAGE = 96;   // ask big; Vinted may return fewer per page
  const WARDROBE_MAX_PAGES = 60;  // ~5.7k listings — far beyond any real wardrobe
  // Wat er bij de kleurstap gebeurde, in gewone taal — belandt in het logboek én
  // in de foutmelding op het dashboard.
  let kleurDiagnose = "the colour step never ran";

  // LET OP — deze twee blokken staan hier bewust, vóór `await getJob()`.
  // Een const wordt pas aangemaakt op het moment dat de uitvoering die regel
  // bereikt. Alles hieronder wordt pas ná de hele publicatie uitgevoerd, dus een
  // hulpwaarde die daar staat bestaat tijdens het invullen nog niet — en dan valt
  // de stap die hem gebruikt om met een harde fout. Zo koos Vinted geen enkele
  // categorie meer (de tabel bestond nog niet) en eindigde de opdracht met
  // "Cannot access 'PRICE_ERR_RE' before initialization".
  // ---- Vinted's eigen categorieboom, letterlijk ----------------------------
  // Deze paden zijn afgelopen in de echte kiezer op vinted.nl (augustus 2026).
  // Het laatste stukje van het pad hoeft geen eindpunt te zijn: staan er nog
  // subcategorieën onder (Jeans → Ripped/Skinny/Slim fit/Straight fit), dan
  // kiest de wandelaar hieronder er zelf een op basis van de artikeltekst.
  const V_KLEDING = {
    // sleutel zonder gender → pad ONDER "<Gender> > Clothing"
    heren: {
      "jeans": ["Jeans"],
      "chinos": ["Trousers"], "broeken": ["Trousers"],
      "shorts": ["Shorts"],
      "t-shirts": ["Tops & t-shirts", "T-shirts"],
      "polo's": ["Tops & t-shirts", "Polo shirts"],
      "overhemden": ["Tops & t-shirts", "Shirts"],
      "truien": ["Jumpers & sweaters"],
      "hoodies": ["Jumpers & sweaters"],
      "jassen": ["Outerwear"],
      "pakken": ["Suits & blazers"],
      "zwembroeken": ["Swimwear"],
      "ondergoed": ["Socks & underwear"],
      "sport tops": ["Activewear", "Tops & t-shirts"],
      "sportbroeken": ["Activewear", "Shorts"],
      "sportjassen": ["Activewear", "Outerwear"],
      "trainingspakken": ["Activewear", "Tracksuits"],
      "hardloopkleding": ["Activewear", "Tops & t-shirts"],
      "wielrenkleding": ["Activewear", "Team shirts & jerseys"],
      "voetbalkleding": ["Activewear", "Team shirts & jerseys"],
      "gymkleding": ["Activewear", "Tops & t-shirts"],
      "skikleding": ["Activewear", "Outerwear"],
      "sportkleding": ["Activewear", "Other activewear"],
    },
    dames: {
      "jeans": ["Jeans"],
      "broeken": ["Trousers & leggings"],
      "shorts": ["Shorts & cropped trousers"],
      "rokken": ["Skirts"],
      "jurken casual": ["Dresses"], "jurken feest": ["Dresses"],
      "blouses": ["Tops & t-shirts"], "tops": ["Tops & t-shirts"],
      "truien": ["Jumpers & sweaters"], "hoodies": ["Jumpers & sweaters"],
      "jassen": ["Outerwear"],
      "zwemkleding": ["Swimwear"],
      "ondergoed": ["Lingerie & nightwear"],
      "sport bh": ["Activewear", "Sports bras"],
      "sportleggings": ["Activewear", "Trousers"],
      "sportbroeken": ["Activewear", "Shorts"],
      "sport tops": ["Activewear", "Tops & t-shirts"],
      "sportjassen": ["Activewear", "Outerwear"],
      "trainingspakken": ["Activewear", "Tracksuits"],
      "hardloopkleding": ["Activewear", "Tops & t-shirts"],
      "wielrenkleding": ["Activewear", "Team shirts & jerseys"],
      "voetbalkleding": ["Activewear", "Team shirts & jerseys"],
      "yogakleding": ["Activewear", "Trousers"],
      "gymkleding": ["Activewear", "Tops & t-shirts"],
      "skikleding": ["Activewear", "Outerwear"],
      "sportkleding": ["Activewear", "Other activewear"],
    },
  };

  // De rode melding onder het prijsveld ("Price must be greater than or equal to
  // 1.0"). Vinted zet die NIET altijd meteen neer: hij kan een halve seconde na
  // het verlaten van het veld verschijnen, en soms pas als het formulier het veld
  // als "aangeraakt" beschouwt. Daarom kijken we ook echt rond het prijsveld zelf
  // (via aria-describedby en de omliggende blokjes) en niet alleen ergens op de
  // pagina — anders werd de melding gemist en dacht de extensie dat de prijs
  // netjes stond, terwijl Vinted hem weigerde.
  const PRICE_ERR_RE = /price must|must be greater|greater than or equal|at least|minimaal|moet (groter|ten minste)|ongeldig|invalid/i;

  // Elke rode regel die het formulier zelf toont ("Fill in size to continue").
  // Bewust smal gehouden: het moet echt LEZEN als een klacht, anders zou een
  // willekeurig element met "error" in de klassenaam een geslaagde opslag
  // alsnog als mislukt laten eindigen.
  const FORM_ERR_RE = /fill in|vul .+ in|is required|required|verplicht|must be|moet |at least|greater than|invalid|ongeldig|select a|kies /i;

  // Welk blad hoort bij dit artikel?
  //
  // WAAROM DIT ZO MOET. De vorige versie keek of een woord uit de optienaam
  // letterlijk in de titel stond. Vinted spelt zijn bladen in het MEERVOUD
  // ("Cardigans", "Checked shirts"), en een titel zegt "Cardigan" — dus die
  // vergelijking mislukte altijd en er werd steevast "Other …" gekozen. Gemeten
  // op drie echte advertenties: een cardigan, een zip-vest en een geruit
  // overhemd belandden alle drie bij "Other". Dat kost vindbaarheid: kopers
  // filteren op deze bladen.
  //
  // Nu: enkelvoud tegen enkelvoud, plus een handjevol woorden die zo
  // vanzelfsprekend zijn dat ze voorrang krijgen.
  //
  // WAAROM HIER EN NIET BIJ kiesBlad. Deze twee stonden vlak boven kiesBlad,
  // ruim duizend regels verderop — en dus ná het punt waar het formulier al
  // wordt ingevuld. Een `const` bestaat pas zodra zijn eigen regel gedraaid is;
  // tot dat moment is hij niet te gebruiken. Het invullen begint bij
  // `await fillForm(item)`, dat is de categoriestap, dat is kiesBlad, en dat is
  // BLAD_VOORKEUR — die dan nog niet bestond. Elke Vinted-advertentie waarbij de
  // categorieboom nog een niveau dieper ging, klapte daarop stuk. Precies de
  // items waar deze lijst voor bedoeld is: cardigans, zip-vesten, geruite
  // overhemden. Alles wat de invulstappen gebruiken hoort dus bóven
  // `const job = await getJob()` te staan; tests/test_vinted_categories.py
  // bewaakt dat.
  const BLAD_VOORKEUR = [
    [/\bcardigan/i,                         /cardigan/i],
    [/\bzip[- ]?(through|up|vest|hoodie)/i, /zip[- ]?through/i],
    // Een half-zip hoort volgens Daniel bij Zip-throughs (31-08-2026). Dat is
    // een verkopersoordeel, geen taalkunde: het staat hier omdat hij het zo
    // verkoopt. Zonder deze regel valt elke half-zip in de restcategorie, want
    // de titel zegt "half zip" en geen enkel blad heet zo.
    [/\b(half|quarter|kwart|halve)[- ]?zip\b|\b1\/[24][- ]?zip\b/i, /zip[- ]?through/i],
    [/\bhoodie/i,                           /^hoodies/i],
    [/\bsweatshirt/i,                       /sweatshirt/i],
    [/\bgeruit|\bchecked|\bplaid|\btartan/i, /check/i],
    [/\bgestreept|\bstriped/i,              /stripe/i],
    [/\bdenim(?!\s*jeans)/i,                /denim/i],
    [/\bflanel|\bflannel/i,                 /flannel/i],
    [/\blinnen|\blinen/i,                   /linen/i],
    [/\boxford/i,                           /oxford/i],
    [/\bpolo\b/i,                           /polo/i],
    [/\bv[- ]?hals|\bv[- ]?neck/i,          /v[- ]?neck/i],
    [/\bronde hals|\bcrew ?neck/i,          /crew ?neck/i],
    [/\bcoltrui|\bturtleneck|\brollkragen/i, /turtleneck|roll ?neck/i],
    [/\bgilet|\bbodywarmer|\bvest\b/i,      /gilet|waistcoat|body ?warmer/i],
    [/\btrenchcoat/i,                       /trench/i],
    [/\bparka/i,                            /parka/i],
    [/\bbomber/i,                           /bomber/i],
    [/\bblazer|\bcolbert/i,                 /blazer/i],
  ];

  // "cardigans" → "cardigan", "shirts" → "shirt". Alleen de kale meervouds-s:
  // slimmer worden helpt hier niet en levert alleen misverstanden op.
  const enkelvoud = (w) => (w.length > 4 && /s$/.test(w) && !/ss$/.test(w) ? w.slice(0, -1) : w);

  const job = await getJob();
  if (!job) return;
  const { id: jobId, serverUrl, payload: item } = job;

  // Inputs we must NEVER clobber when filling dynamic attribute fields.
  const PROTECTED = [
    'input[data-testid="title--input"]',
    'textarea[data-testid="description--input"]',
    'input[data-testid="price-input--input"]',
    'input[data-testid="catalog-select-dropdown-input"]',
  ];
  const isProtected = (el) => !!el && PROTECTED.some((s) => el.matches?.(s));

  try {
    if (job.action === "delete") {
      await deleteListingVinted(item.platform_listing_id);
      send("JOB_DONE", {});
    } else if (job.action === "content_refresh") {
      await refreshListingVinted(item);
      send("JOB_DONE", {});
    } else {
      // Staat dit item al online? Dat gebeurt als de verkoper hem zelf heeft
      // geplaatst nadat de automatische poging bleef hangen. Dan niet nóg een
      // keer plaatsen (dubbele advertentie), maar de bestaande koppelen en de
      // opdracht netjes afsluiten — daarmee verdwijnt ook het "Publishing now…"
      // kaartje dat anders eeuwig bleef staan.
      const already = await resolveCreatedVintedItem(item, item.platform_listing_id, 2500, { exact: true })
        .catch(() => null);
      if (already) {
        console.log(`[Omnivaleur] Vinted create: "${item.title}" staat al online (${already.id}) — koppelen in plaats van opnieuw plaatsen`);
        send("JOB_DONE", {
          platform_listing_id: already.id,
          platform_listing_url: `${location.origin}/items/${already.id}`,
          note: "already_published_manually",
        });
        return;
      }
      // STAAT HET FORMULIER ER EIGENLIJK WEL? (Budgetheld, 01-09-2026)
      //
      // Uitgelogd — of op een onderhouds-/tussenpagina — geeft Vinted op
      // /items/new gewoon een pagina terug, alleen zonder plaatsformulier. Alle
      // invulstappen mislukken dan stil (step() logt en gaat door), en de
      // controle hieronder klaagt óók niet: die kijkt of een veld leeg is, en
      // een veld dat er niet ís, is niet leeg. Zo kon een advertentie als
      // geplaatst worden afgemeld terwijl er nooit een formulier was. De titel
      // is het veld dat op elk Vinted-formulier staat; ontbreekt die, dan is dit
      // geen plaatsformulier en stoppen we vóórdat er iets afgemeld kan worden.
      await waitForEl('input[data-testid="title--input"]', 20000).catch(() => null);
      if (!qs('input[data-testid="title--input"]')) {
        const ingelogd = document.querySelector('a[href*="/member/"], #user-menu-button, [data-testid="user-menu-button"]');
        throw new Error(ingelogd
          ? `The Vinted listing form did not load on ${location.href} — nothing was published. Open Vinted yourself and try again.`
          : `You are not signed in to Vinted on ${location.origin} — nothing was published. Log in to Vinted in this browser and publish again.`);
      }
      await fillForm(item);
      // Controleer de velden waar Vinted op blokkeert vóór we opsturen. Bleef er
      // iets leeg, dan stoppen we met een melding die zegt wát er ontbrak en met
      // welke waarde het niet lukte — een stille mislukking kostte alleen maar
      // tijd, want het formulier ging tóch niet door de validatie.
      const gaps = [];
      const sizeEl = qs('input[data-testid="category-size-single-grid-input"]');
      const colEl = qs('input[data-testid="color-select-dropdown-input"]');
      const descEl = qs('textarea[data-testid="description--input"]');
      const prijsFout = priceErrorVinted();
      // De melding gaat één op één naar het dashboard, en dat is Engels. Half
      // Nederlands, half Engels leest als een storing in plaats van als uitleg.
      if (prijsFout) gaps.push(`price (${item.price} — Vinted says: ${prijsFout})`);
      if (descEl && !(descEl.value || "").trim()) gaps.push("description");
      if (sizeEl && !(sizeEl.value || "").trim()) gaps.push(`size (${item.size || "empty"})`);
      if (colEl && !(colEl.value || "").trim()) {
        // Neem meteen mee wat we op dat moment ZAGEN, anders is de melding niet
        // te herleiden zonder de gebruiker om een schermafbeelding te vragen.
        gaps.push(`colour (${item.color || "empty"} — ${kleurDiagnose})`);
      }
      if (gaps.length) {
        throw new Error("Vinted wouldn't accept these fields: " + gaps.join(", ") +
                        ". The tab is left open — fill them in yourself and click Upload, " +
                        "and this listing is marked as published automatically.");
      }
      let id;
      try {
        id = await submitListing(/\/items\/(\d+)/);
      } catch (submitErr) {
        // Een blokkade (adres / telefoon) betekent dat er niets geplaatst IS.
        // De garderobe afzoeken kost dan anderhalve minuut om te bevestigen wat
        // we al weten, en houdt ondertussen de hele wachtrij bezet.
        if (submitErr && submitErr.blokkade) throw submitErr;
        // Vinted's post-upload "check in progress" review can delay the
        // /items/{id} redirect past submitListing's wait, so a timeout here does
        // NOT mean the listing failed. Confirm via the wardrobe before giving up:
        // the item appears there (as is_processing) within a minute or two, and
        // we recover its real id. Only if it never shows up is it a real failure.
        const recovered = await resolveCreatedVintedItem(item, item.platform_listing_id, 90000).catch(() => null);
        if (!recovered) throw submitErr;
        id = recovered.id;
        console.log(`[Omnivaleur] Vinted create: recovered id ${id} via wardrobe after delayed redirect${recovered.processing ? " (still in Vinted review)" : ""}`);
      }
      // Use the origin we actually ended up on (Vinted redirects to the
      // account's country domain), so the stored URL is the real one this
      // item lives on — critical for a later delete to hit the right domain.
      send("JOB_DONE", { platform_listing_id: id, platform_listing_url: `${location.origin}/items/${id}` });
    }
  } catch (e) {
    send("JOB_ERROR", null, String(e));
  }

  // Light in-place edit: re-order the photos (a real change Vinted re-indexes on)
  // WITHOUT touching the seller's price, title, description or category — so it
  // can't misrepresent the item, change what it's listed for, or look like a
  // duplicate listing. Price is only filled if the page shows €0 (imports).
  async function refreshListingVinted(item) {
    await waitForEl('input[data-testid="price-input--input"], input[data-testid="title--input"]', 20000);
    await sleep(800);
    const priceEl = qs('input[data-testid="price-input--input"]');
    if (!priceEl) throw new Error("Vinted edit: price field not found on the edit page");

    // A price-sync job is the one case where changing the price IS the point:
    // the dashboard just repriced this item and the whole job exists to carry
    // that to Vinted. Every other refresh keeps the seller's price untouched.
    const pageNow = _num(priceEl.value);
    if (item._price_update) {
      const target = Number(item.price);
      if (!(isFinite(target) && target >= 1)) {
        throw new Error("Vinted price update: the new price must be €1.00 or more.");
      }
      if (Math.abs(pageNow - target) >= 0.01) {
        const ok = await fillPriceVinted(target);
        if (!ok) throw new Error("Vinted price update: the price field wouldn't accept the new price.");
      }
    } else if (!(isFinite(pageNow) && pageNow >= 1)) {
      // Only fill the price when the page shows €0/blank (typical for imported
      // items), using the dashboard price, so the save isn't blocked by
      // Vinted's ">= 1.0" rule.
      const target = Number(item.price);
      if (!(isFinite(target) && target >= 1)) {
        throw new Error("Vinted refresh aborted: the listing shows €0 and there's no dashboard price to fall back on. Set a price on the item first.");
      }
      const ok = await fillPriceVinted(target);
      if (!ok) throw new Error("Vinted refresh aborted: the listing had no price and it couldn't be filled from the dashboard.");
    }

    // The actual, price-safe refresh: re-order the uploaded photos. This is the
    // only edit we make, and we verify it truly changed the on-page order — if
    // it didn't, we throw rather than save-and-report-success on a no-op.
    // A price update is exempt: the price IS the change, so demanding a photo
    // shuffle on top would fail every item with fewer than three photos.
    const reordered = item._price_update ? true : await reorderPhotosVinted();
    if (!reordered) {
      throw new Error("Vinted refresh: couldn't re-order the photos while keeping the first one fixed. This needs at least 3 photos, and Vinted must accept the drag. Nothing was changed — use refresh 2 (relist) instead.");
    }

    // Vinted keurt bij het opslaan de HELE advertentie, niet alleen het veld dat
    // wij veranderden. Een oudere of geïmporteerde advertentie die een inmiddels
    // verplicht veld mist — meestal de maat — wordt daarom geweigerd: het
    // formulier blijft gewoon staan met "Fill in size to continue" eronder. Van
    // buitenaf is dat niet te onderscheiden van "hij drukt niet op opslaan", en
    // precies zo werd het gemeld. Dus eerst aanvullen wat we uit het dashboard
    // kunnen halen; wat dan nog ontbreekt, staat straks met naam in de fout.
    await topUpRequiredFieldsVinted(item);

    // Save/update button — Vinted's edit page uses the same testid as create ("Save"/"Update").
    const saveBtn = [...document.querySelectorAll('button[data-testid], button')]
      .find(b => b.offsetParent !== null && /^(save|update|opslaan|bijwerken)$/i.test(b.textContent.trim()));
    if (!saveBtn) throw new Error("Vinted edit: save/update button not found");
    await sleep(300);
    saveBtn.click();

    // Verify the save actually went through instead of blindly reporting success.
    // Failure signals we watch for: the price field flips aria-invalid, a visible
    // validation/error message appears, or we simply stay on the edit form. A real
    // save either navigates away from the edit page or closes the price field.
    for (let i = 0; i < 12; i++) {
      await sleep(600);
      const stillEditing = qs('input[data-testid="price-input--input"]');
      if (!stillEditing) return; // navigated away → saved
      if (stillEditing.getAttribute("aria-invalid") === "true" || _num(stillEditing.value) < 1) {
        throw new Error("Vinted refresh: save was rejected — the price is invalid (Vinted requires €1.00 or more).");
      }
      // Elke klacht van het formulier telt, niet alleen die over de prijs. Een
      // geweigerde opslag om een leeg maatveld gaf hiervoor de nietszeggende
      // "could not be verified" terug, terwijl Vinted er letterlijk bij zette
      // wat er miste.
      const klachten = formErrorsVinted();
      if (klachten.length) {
        throw new Error("Vinted refresh: save was rejected — " + klachten.join(" · ") + saveHintVinted(item, klachten));
      }
    }
    // Still on the edit form after ~7s with no visible error — treat as failure
    // rather than falsely reporting success (nothing verified as saved).
    // Zonder zichtbare melding kunnen we nog steeds zeggen wélk verplicht veld
    // leeg staat; dat is negen van de tien keer waar Vinted op blokkeert.
    const nogLeeg = emptyRequiredFieldsVinted();
    throw new Error("Vinted refresh: clicked Save but the edit form never closed — the update could not be verified." +
      (nogLeeg.length ? " Still empty on the Vinted form: " + nogLeeg.join(", ") + "." : "") +
      saveHintVinted(item, nogLeeg));
  }

  // Vult velden aan die op de Vinted-pagina leeg staan, met wat het dashboard
  // van dit item weet. Raakt uitsluitend LEGE velden aan — wat de verkoper daar
  // zelf heeft staan blijft onaangeroerd, ook bij een prijswijziging.
  async function topUpRequiredFieldsVinted(item) {
    const gevuld = [];
    const maatVeld = () => qs('input[data-testid="category-size-single-grid-input"]')
      || [...document.querySelectorAll('input[data-testid^="category-size"][data-testid$="-input"]')]
        .find(e => e.offsetParent) || null;

    if (maatVeld() && !sizeIsFilledVinted() && String(item.size || "").trim()) {
      // Dezelfde herhaling als bij het plaatsen: welke vorm het maatveld
      // aanneemt hangt van de categorie af, en één poging is geregeld te vroeg.
      for (let poging = 0; poging < 3 && !sizeIsFilledVinted(); poging++) {
        await fillAttributeVinted(["size"], String(item.size));
        await sleep(500);
      }
      if (sizeIsFilledVinted()) gevuld.push("size");
      else console.warn("[Omnivaleur] Vinted edit: maat bleef leeg na herhalen:", item.size);
    }

    if (gevuld.length) {
      clog("edit: leeg veld aangevuld vóór opslaan — " + gevuld.join(", "));
      // Laat geen open paneel over de opslaanknop heen staan.
      const buiten = qs('input[data-testid="title--input"]');
      if (buiten) { realClickEl(buiten); await sleep(400); }
    }
    return gevuld;
  }

  // Waar klaagt het formulier over, in Vinted's eigen woorden?
  function formErrorsVinted() {
    const gezien = new Set();
    const regels = [];
    for (const e of document.querySelectorAll('[class*="validation" i], [role="alert"], [class*="error" i]')) {
      if (e.offsetParent === null) continue;
      const t = (e.textContent || "").replace(/\s+/g, " ").trim();
      if (!t || t.length > 160 || gezien.has(t) || !FORM_ERR_RE.test(t)) continue;
      gezien.add(t);
      regels.push(t);
    }
    // Alleen de meest specifieke regels: een omhullend blok herhaalt de tekst
    // van zijn kind, en dan zou dezelfde klacht er twee keer in staan.
    return regels.filter(t => !regels.some(o => o !== t && t.includes(o)));
  }

  // Welke velden waar Vinted op blokkeert staan op dit moment zichtbaar leeg.
  function emptyRequiredFieldsVinted() {
    const leeg = [];
    const maat = qs('input[data-testid="category-size-single-grid-input"]')
      || [...document.querySelectorAll('input[data-testid^="category-size"][data-testid$="-input"]')]
        .find(e => e.offsetParent);
    if (maat && !(maat.value || "").trim()) leeg.push("size");
    for (const [naam, sel] of [
      ["colour",    'input[data-testid="color-select-dropdown-input"]'],
      ["condition", 'input[data-testid="category-condition-single-list-input"]'],
      ["category",  'input[data-testid="catalog-select-dropdown-input"]'],
    ]) {
      const el = qs(sel);
      if (el && el.offsetParent !== null && !(el.value || "").trim()) leeg.push(naam);
    }
    return leeg;
  }

  // Eén regel die de gebruiker écht verder helpt. Verreweg het vaakst: Vinted
  // wil een maat op een advertentie die er nooit een had, en het item in
  // Omnivaleur heeft er ook geen — dan lost opnieuw proberen niets op.
  function saveHintVinted(item, klachten) {
    const tekst = (klachten || []).join(" ").toLowerCase();
    if (!/size|maat/.test(tekst)) return "";
    return String(item.size || "").trim()
      ? ` Omnivaleur has size "${item.size}" for this item but Vinted wouldn't accept it — set the size on the Vinted page yourself and click Save.`
      : " This item has no size in Omnivaleur, so it can't be filled in for you — add the size to the item and try again.";
  }

  // Locate the uploaded-photo tiles on the edit page. Verified live against
  // Vinted's edit DOM (2026-07): the photos live in [data-testid="media-upload-grid"]
  // and each draggable tile is a ".u-cursor-grab" wrapping [data-testid="image-wrapper-N"].
  // Scoping to that grid is essential — a broad img search also matches the site
  // logo and the account avatar, which must never be treated as photo tiles.
  function findPhotoTiles() {
    const grid = document.querySelector('[data-testid="media-upload-grid"], .media-select__grid');
    if (grid) {
      const grabs = [...grid.querySelectorAll('.u-cursor-grab')]
        .filter((t) => t.offsetParent !== null && t.querySelector("img"));
      if (grabs.length >= 2) return grabs;
      // Same grid, but pin to the numbered image wrappers if the grab class drifts.
      const wraps = [...grid.querySelectorAll('[data-testid^="image-wrapper-"]')]
        .filter((t) => t.offsetParent !== null && t.querySelector("img"));
      if (wraps.length >= 2) return wraps;
    }
    // Last-resort fallback if the grid testid changes: any draggable tile with an
    // <img>, but NOT scoped to a header/nav so we skip the logo/avatar.
    const loose = [...document.querySelectorAll('.u-cursor-grab, [draggable="true"]')]
      .filter((t) => t.offsetParent !== null && t.querySelector?.("img") &&
                     !t.closest("header, nav, [class*='header' i], [class*='Header' i]"));
    return loose.length >= 2 ? loose : [];
  }

  // Signature of the current photo order (last chars of each src) so we can prove
  // a re-order actually happened rather than trusting the drag blindly.
  function photoOrderSig() {
    return findPhotoTiles().map((t) => {
      const im = t.querySelector("img");
      return (im?.currentSrc || im?.src || "").slice(-48);
    }).join("|");
  }

  // Pointer-based drag (dnd-kit / most modern React sortables listen to pointer
  // events, NOT native HTML5 drag). Moves src onto dst in several small steps.
  async function pointerDragTile(src, dst) {
    const r1 = src.getBoundingClientRect(), r2 = dst.getBoundingClientRect();
    const from = { x: r1.left + r1.width / 2, y: r1.top + r1.height / 2 };
    const to = { x: r2.left + r2.width / 2, y: r2.top + r2.height / 2 };
    const ev = (x, y, extra = {}) => ({ bubbles: true, cancelable: true, composed: true,
      clientX: x, clientY: y, pointerId: 1, pointerType: "mouse", isPrimary: true,
      button: 0, buttons: 1, ...extra });
    src.dispatchEvent(new PointerEvent("pointerdown", ev(from.x, from.y)));
    src.dispatchEvent(new MouseEvent("mousedown", ev(from.x, from.y)));
    await sleep(150);
    const steps = 10;
    for (let i = 1; i <= steps; i++) {
      const x = from.x + (to.x - from.x) * (i / steps);
      const y = from.y + (to.y - from.y) * (i / steps);
      const over = document.elementFromPoint(x, y) || dst;
      over.dispatchEvent(new PointerEvent("pointermove", ev(x, y)));
      over.dispatchEvent(new MouseEvent("mousemove", ev(x, y)));
      await sleep(55);
    }
    dst.dispatchEvent(new PointerEvent("pointerup", ev(to.x, to.y, { buttons: 0 })));
    dst.dispatchEvent(new MouseEvent("mouseup", ev(to.x, to.y, { buttons: 0 })));
  }

  // Native HTML5 drag-and-drop fallback (for sortables that use the DnD API).
  async function html5DragTile(src, dst) {
    const dt = new DataTransfer();
    const r1 = src.getBoundingClientRect(), r2 = dst.getBoundingClientRect();
    const fire = (type, el, r) => el.dispatchEvent(new DragEvent(type, {
      bubbles: true, cancelable: true, composed: true, dataTransfer: dt,
      clientX: r.left + r.width / 2, clientY: r.top + r.height / 2 }));
    fire("dragstart", src, r1); await sleep(100);
    fire("dragenter", dst, r2); await sleep(100);
    fire("dragover", dst, r2); await sleep(100);
    fire("drop", dst, r2); await sleep(100);
    fire("dragend", src, r1);
  }

  // Re-order the listing's photos WITHOUT ever moving the first (main) photo —
  // that's usually the most important one, so we leave it pinned in place and
  // only shuffle the rest. We move the SECOND photo to the end. This needs at
  // least 3 photos (with 2, any change would touch the first). Verifies the
  // order actually changed AND that photo #1 is unchanged; returns false if it
  // couldn't, so the caller fails honestly instead of saving a no-op.
  async function reorderPhotosVinted() {
    let tiles = findPhotoTiles();
    if (tiles.length < 3) return false; // can't reorder photos 2..N and keep #1 fixed
    const before = photoOrderSig();
    const firstBefore = before.split("|")[0];

    const changedAndFirstIntact = () => {
      const sig = photoOrderSig();
      return sig !== before && sig.split("|")[0] === firstBefore;
    };

    // Move the second photo to the end (pointer drag first, HTML5 as fallback).
    await pointerDragTile(tiles[1], tiles[tiles.length - 1]);
    await sleep(700);
    if (changedAndFirstIntact()) return true;

    tiles = findPhotoTiles();
    if (tiles.length < 3) return false;
    await html5DragTile(tiles[1], tiles[tiles.length - 1]);
    await sleep(700);
    return changedAndFirstIntact();
  }

  // A testid that belongs to a PHOTO remove button ("×" on each thumbnail on the
  // edit page: media-select-grid-delete-button-N), NOT the delete-listing button.
  // Matching these by a loose "delete" substring would delete a photo instead of
  // the listing — verified live 2026-07. Always exclude them.

  // Find the seller's "Delete listing" control on the current item page. The real
  // control has the exact testid "item-delete-button" (verified live 2026-07) and
  // opens a confirm dialog with item-delete-confirmation-button / -cancelation-button.
  // Returns the clickable element (or a {__needsOpen} wrapper), or null.
  function findDeleteEntryPoint() {
    // Layer 1: the exact delete-listing button, matched by its precise testid.
    // It can render briefly hidden (0x0) before the item-details panel lays out,
    // so we accept it regardless of current visibility and scroll it into view
    // before clicking (see deleteListingVinted). NEVER a loose "delete" match —
    // that hits the per-photo remove buttons on the edit page.
    const exact = document.querySelector('[data-testid="item-delete-button"]');
    if (exact) return exact;

    // Layer 2: open a kebab/"..."/actions dropdown, then look inside it (older layouts).
    const actionsBtn = document.querySelector(
      '[data-testid="item-actions-button"], [data-testid="item-menu-button"], ' +
      '[data-testid="item-page-actions-dropdown-button"], [data-testid*="kebab"], ' +
      'button[aria-label*="more" i], button[aria-label*="actions" i], button[aria-label*="options" i]'
    ) || [...document.querySelectorAll('button')].find(b =>
      b.offsetParent !== null && b.querySelector('svg') && !b.textContent.trim() &&
      /kebab|dots|more|menu/i.test(b.className + " " + (b.getAttribute("aria-label") || ""))
    );
    if (actionsBtn) return { __needsOpen: actionsBtn };

    // Layer 3: a visible button/link literally labelled "Delete" (whole word) —
    // but never a per-photo remove button (those carry no text but we guard anyway).
    const el = [...document.querySelectorAll('button, a, [role="menuitem"], [role="button"]')]
      .find(e => e.offsetParent !== null && !isPhotoDeleteTestid(e.dataset.testid) &&
                 /^\s*delete\s*$/i.test(e.textContent));
    if (el) return el;

    return null;
  }

  // Discover the logged-in member id from the item page (you are the seller of
  // your own item). Needed for the wardrobe endpoint, which is the ONLY item
  // API we've confirmed works reliably on the country domain (the single-item
  // /api/v2/items/{id} endpoint 404s even for a live own-item, so we can't
  // trust it for verification).
  async function getVintedUserId() {
    let id = null;
    for (const a of document.querySelectorAll('a[href*="/member/"]')) {
      const m = (a.getAttribute("href") || "").match(/\/member\/(\d+)/);
      if (m) { id = m[1]; break; }
    }
    if (id) return id;
    // Fall back to opening the account menu, which exposes /member/{id}.
    document.querySelector('#user-menu-button, [data-testid="user-menu-button"]')?.click();
    await sleep(600);
    for (const a of document.querySelectorAll('a[href*="/member/"]')) {
      const m = (a.getAttribute("href") || "").match(/\/member\/(\d+)/);
      if (m) { id = m[1]; break; }
    }
    return id;
  }

  // Is this listing id currently present in the user's own wardrobe (i.e. still
  // live)? Returns true/false, or null if we couldn't read the wardrobe at all.
  //
  // MUST page through the whole wardrobe: Vinted caps per_page server-side and
  // silently returns fewer items than asked, so a single "page=1&per_page=200"
  // call only ever proves the NEWEST slice. Older listings fell outside it and
  // were reported absent, which aborted their delete ("not in your wardrobe")
  // even though they were live — verified live 2026-07 on item 8557510561.
  // Only "walked every page without a hit" may return false; any page that
  // fails to load returns null (unknown), never false.

  async function isInWardrobe(userId, listingId) {
    const want = String(listingId);
    try {
      for (let page = 1; page <= WARDROBE_MAX_PAGES; page++) {
        const res = await fetch(
          `/api/v2/wardrobe/${userId}/items?order=newest_first&page=${page}&per_page=${WARDROBE_PER_PAGE}`,
          { headers: { Accept: "application/json" } }
        );
        if (!res.ok) return null;
        const data = await res.json();
        if (data.code && data.code !== 0) return null;
        const items = data.items || [];
        if (items.some(it => String(it.id) === want)) return true;

        // Stop when the wardrobe is exhausted. Prefer Vinted's own pagination
        // metadata; fall back to "short/empty page means last page".
        const pg = data.pagination || {};
        if (items.length === 0) return false;
        if (pg.total_pages && page >= pg.total_pages) return false;
        if (!pg.total_pages && items.length < WARDROBE_PER_PAGE) return false;
      }
      // Ran out of pages without ever seeing the end — we cannot honestly claim
      // the item is absent, so report "unknown" rather than a false negative.
      return null;
    } catch (e) {
      return null;
    }
  }

  // After clicking Upload, Vinted often runs a "check in progress" review before
  // it redirects to /items/{id} — so submitListing's URL-wait can time out even
  // though the item WAS created (it goes live minutes later). Rather than falsely
  // reporting "Relist failed", we confirm the item exists by finding it in the
  // wardrobe (it shows up there as is_processing within a minute or two) and
  // recover its real id. Returns {id} or null if it truly never appeared.
  // `excludeId` is the old (deleted) listing id on a relist, so we never mistake
  // it for the new one.
  async function resolveCreatedVintedItem(item, excludeId, timeoutMs, opts = {}) {
    const norm = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9]/g, "");
    const target = norm(item.title);
    if (!target) return null;

    const userId = await getVintedUserId();
    if (!userId) return null;

    const deadline = Date.now() + timeoutMs;
    // First pass immediately, then poll — the item can take a moment to register.
    while (Date.now() < deadline) {
      try {
        const res = await fetch(
          `/api/v2/wardrobe/${userId}/items?order=newest_first&page=1&per_page=50`,
          { headers: { Accept: "application/json" } }
        );
        if (res.ok) {
          const data = await res.json();
          const items = (data && data.items) || [];
          // newest_first → the first title match that isn't the old listing is
          // the one we just created (a relist posts exactly one new item).
          const hit = items.find((it) => {
            if (String(it.id) === String(excludeId)) return false;
            // Verkochte, beëindigde en concept-advertenties tellen niet mee: die
            // staan wel in de garderobe maar zijn niet "het item staat online".
            if (it.is_closed || it.is_draft) return false;
            const t = norm(it.title);
            if (!t) return false;
            // exact: alleen een volledig gelijke titel telt. Gebruikt door de
            // controle vooraf, waar een losse gelijkenis het verkeerde item aan
            // de advertentie zou kunnen koppelen.
            return opts.exact ? t === target : (t.includes(target) || target.includes(t));
          });
          if (hit) return { id: String(hit.id), processing: !!hit.is_processing };
        }
      } catch (_) { /* transient — keep polling */ }
      await sleep(3000);
    }
    return null;
  }

  async function deleteListingVinted(listingId) {
    // We're on the item page on its real country origin (e.g. vinted.nl) —
    // getDeleteUrl now navigates to the stored listing URL, so location.origin
    // is the domain where this item AND the wardrobe API actually live.
    await waitForEl('[data-testid="item-details"], .item-details, main', 15000);
    await sleep(1000);

    // Establish ground truth BEFORE deleting: the item must be present in the
    // user's own wardrobe on this origin. If we can't confirm that, we refuse
    // to proceed rather than click blindly and risk a false success.
    const userId = await getVintedUserId();
    if (!userId) throw new Error("Could not determine your Vinted member id on " + location.origin + " — make sure you're logged into this Vinted account.");

    const presentBefore = await isInWardrobe(userId, listingId);
    if (presentBefore === null) throw new Error(`Could not read your Vinted wardrobe on ${location.origin} to verify item ${listingId} — aborting to avoid an unverified delete.`);
    if (presentBefore === false) throw new Error(`Vinted item ${listingId} is not in your wardrobe on ${location.origin} — it may already be gone or belong to a different account; nothing to delete.`);

    // The click → confirm → verify sequence is retried a few times: the most
    // common relist-delete failures are transient (the actions menu didn't open,
    // the confirm modal rendered a beat late, or the wardrobe API lagged behind
    // the delete). Each attempt re-locates the control from scratch on the SAME
    // page load — Vinted's own confirm dialog is idempotent, and every attempt
    // re-verifies against the wardrobe, so a retry can never double-delete or
    // report a false success. Only after all attempts fail do we surface an error.
    const MAX_DELETE_ATTEMPTS = 3;
    let lastErr = null;
    for (let attempt = 1; attempt <= MAX_DELETE_ATTEMPTS; attempt++) {
      try {
        // If a previous attempt's click already removed it, we're done — verify
        // and stop before clicking anything again.
        if (attempt > 1 && (await isInWardrobe(userId, listingId)) === false) return;

        await _attemptDeleteClickAndConfirm(listingId);

        // Verify the item is actually gone from the wardrobe before reporting
        // success — the same reliable endpoint we used for the pre-check.
        // Wardrobe can lag a moment after delete, so poll a few times.
        let goneAfter = false;
        for (let i = 0; i < 4; i++) {
          const present = await isInWardrobe(userId, listingId);
          if (present === false) { goneAfter = true; break; }
          if (present === null) throw new Error(`Could not re-read your Vinted wardrobe on ${location.origin} to confirm deletion of ${listingId}.`);
          await sleep(1500);
        }
        if (goneAfter) return;  // confirmed removed — success
        throw new Error(`Vinted listing ${listingId} is still in your wardrobe after confirming delete — removal was not verified`);
      } catch (e) {
        lastErr = e;
        if (attempt < MAX_DELETE_ATTEMPTS) {
          // Close any half-open menu/modal so the next attempt starts clean, then
          // give the page a moment to settle before re-locating the control.
          document.querySelector('[data-testid="item-delete-cancelation-button"]')?.click();
          document.body?.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
          await sleep(1500);
        }
      }
    }
    throw lastErr || new Error(`Could not delete Vinted listing ${listingId} after ${MAX_DELETE_ATTEMPTS} attempts`);
  }

  // One delete attempt: (re)locate the delete control, click it, and confirm in
  // the modal. Split out of deleteListingVinted so the whole click→confirm
  // sequence can be retried cleanly on a transient failure. Throws on any missing
  // control; never verifies success itself (the caller polls the wardrobe).
  async function _attemptDeleteClickAndConfirm(listingId) {
    // Wait specifically for the delete-listing button to exist (it renders a beat
    // after the item-details panel), then locate the entry point.
    await waitForEl('[data-testid="item-delete-button"], [data-testid="item-actions-button"], [data-testid="item-menu-button"]', 8000).catch(() => {});
    let entry = findDeleteEntryPoint();

    if (!entry) throw new Error("Delete control not found on Vinted item page for ID " + listingId + " — Vinted may have changed its page layout");

    let deleteEl;
    if (entry.__needsOpen) {
      entry.__needsOpen.click();
      await sleep(600);
      const menu = document.querySelector('[role="menu"], [role="listbox"], [data-testid*="dropdown"], [data-testid*="modal"]') || document;
      deleteEl = menu.querySelector('[data-testid="item-delete-button"]')
        || [...menu.querySelectorAll('button, a, [role="menuitem"]')]
          .find(el => !isPhotoDeleteTestid(el.dataset.testid) && /^\s*delete\s*$/i.test(el.textContent));
      if (!deleteEl) throw new Error("Delete option not found in Vinted actions menu for ID " + listingId);
    } else {
      deleteEl = entry;
    }
    // The button can be laid out at 0x0 until scrolled into view; force layout so
    // the click reliably opens the confirm dialog.
    deleteEl.scrollIntoView({ block: "center" });
    await sleep(300);
    deleteEl.click();
    await sleep(1000);

    // Confirm in the modal — required, not optional. The real dialog exposes the
    // exact testid item-delete-confirmation-button (button reads "Confirm and
    // delete") alongside item-delete-cancelation-button ("Cancel"). Prefer the
    // exact confirm testid; only fall back to text matching, and NEVER match the
    // cancel button or a per-photo remove button. Wait briefly for it to render.
    let confirmBtn = null;
    for (let i = 0; i < 6 && !confirmBtn; i++) {
      const confirmScope = document.querySelector('[role="dialog"], [role="alertdialog"], [data-testid*="modal"], .ReactModal__Content') || document;
      confirmBtn = confirmScope.querySelector('[data-testid="item-delete-confirmation-button"]')
        || [...confirmScope.querySelectorAll('button, a[role="button"]')]
          .find(el => {
            const t = el.textContent.trim();
            const tid = el.dataset.testid || "";
            if (/annuleer|cancel|terug|back/i.test(t) || /cancel/i.test(tid) || isPhotoDeleteTestid(tid)) return false;
            return /confirm|delete|verwijder|remove|\byes\b|\bja\b/i.test(t) || tid === "item-delete-confirmation-button";
          });
      if (!confirmBtn) await sleep(500);
    }
    if (!confirmBtn) throw new Error("Confirm-delete button not found on Vinted for ID " + listingId + " — deletion was not confirmed");
    confirmBtn.click();
    await sleep(1500);
  }

  // Sommige tegels (kleur) reageren pas nadat de muis er echt overheen is
  // bewogen: React zet zijn klik-handler pas bij hover. Een kale click-reeks
  // wordt dan genegeerd — precies het gedrag waarbij de kleur leeg bleef.
  function humanClickEl(el) {
    if (!el) return;
    const r = el.getBoundingClientRect();
    const o = { bubbles: true, cancelable: true, view: window,
      clientX: r.left + r.width / 2, clientY: r.top + r.height / 2 };
    el.dispatchEvent(new PointerEvent("pointerover", o));
    el.dispatchEvent(new MouseEvent("mouseover", o));
    el.dispatchEvent(new PointerEvent("pointermove", o));
    el.dispatchEvent(new MouseEvent("mousemove", o));
    realClickEl(el);
  }

  function realClickEl(el) {
    if (!el) return;
    const r = el.getBoundingClientRect();
    const o = { bubbles: true, cancelable: true, view: window,
      clientX: r.left + r.width / 2, clientY: r.top + r.height / 2 };
    for (const t of ["pointerdown", "mousedown", "pointerup", "mouseup", "click"]) {
      el.dispatchEvent(new (t.startsWith("pointer") ? PointerEvent : MouseEvent)(t, o));
    }
  }

  // Has Vinted accepted a size? Its size trigger is a readonly input whose value
  // holds the chosen size ("M"), empty as long as the field is untouched.
  function sizeIsFilledVinted() {
    const el = document.querySelector('input[data-testid="category-size-single-grid-input"]')
      || [...document.querySelectorAll('input[data-testid^="category-size"][data-testid$="-input"]')]
        .find(e => e.offsetParent);
    return !!(el && (el.value || "").trim());
  }

  async function fillForm(item) {
    await waitForEl('input[data-testid="title--input"]', 20000);
    await step("title",       () => fillInput(qs('input[data-testid="title--input"]'), (item.title || "").slice(0, 100)));
    await step("description", () => fillDescription(['textarea[data-testid="description--input"]'], item.description));
    // Photos FIRST: Vinted generates the "Suggested" categories from the uploaded
    // images, so the suggestions don't exist until the photos finish loading.
    await step("photos",      () => item.photo_urls?.length && uploadPhotos(item.photo_urls.slice(0, 20), { jitter: true }));
    await sleep(1500); // let Vinted run image recognition and render the suggestions
    await step("category",    () => fillCategoryVinted(item));
    await sleep(500); // category drives which attribute fields (size/brand/condition) render
    await step("price",       () => fillPriceVinted(item.price));
    await step("condition",   () => fillAttributeVinted(["condition", "status"], CONDITION_MAP[(item.condition || "").toLowerCase()] || CONDITION_MAP["good"]));
    // Size: the field only renders once the category is settled, and which shape
    // it takes (grid or dropdown) depends on that category — so one attempt was
    // regularly too early and the listing came out with "Fill in size to continue".
    await step("size", async () => {
      if (!item.size) return false;
      for (let attempt = 0; attempt < 3; attempt++) {
        if (sizeIsFilledVinted()) return true;
        await fillAttributeVinted(["size"], String(item.size));
        await sleep(500);
        if (sizeIsFilledVinted()) return true;
        await sleep(800); // give the category-driven field time to (re)render
      }
      console.warn("[Omnivaleur] Vinted size still empty after retries:", item.size);
      return false;
    });
    await step("brand",       () => item.brand && fillAttributeVinted(["brand"], item.brand));
    await step("colour",      () => fillColourVinted(item));
    // Colour accordion only commits when another attribute trigger is realClicked.
    // Always open the material trigger to commit the colour selection.
    await sleep(200);
    const matTriggerEl = qs('input[data-testid="category-material-multi-list-input"]');
    // Scroll first: a click on an off-screen trigger is ignored by Vinted.
    if (matTriggerEl) { matTriggerEl.scrollIntoView({ block: "center" }); await sleep(250); realClickEl(matTriggerEl); await sleep(700); }
    if (item.material) {
      await step("material", () => fillMaterialFromOpenPanel(item.material));
    }
    // Close material panel.
    // Strategy: realClick the title input (outside the dropdown) to trigger click-outside dismissal.
    // This is unconditional — even if no material was set, the panel was opened to commit colour.
    await sleep(200);
    const titleInputEl = qs('input[data-testid="title--input"]');
    if (titleInputEl) {
      realClickEl(titleInputEl);
      await sleep(500);
    }
    // If panel still shows Cell__title items, try Escape.
    if (document.querySelector('[class*="web_ui__Cell__title"]')) {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }));
      await sleep(400);
    }
    // Final fallback: toggle-click the trigger.
    if (document.querySelector('[class*="web_ui__Cell__title"]') && matTriggerEl) {
      realClickEl(matTriggerEl);
      await sleep(500);
    }

    // Final guard: re-assert title in case any attribute step touched it.
    const titleEl = qs('input[data-testid="title--input"]');
    const wantTitle = (item.title || "").slice(0, 100);
    if (titleEl && titleEl.value !== wantTitle) {
      fillInput(titleEl, wantTitle);
    }

    await repairEmptyFieldsVinted(item, wantTitle);
  }

  // Eindcontrole met herstel.
  //
  // Vinted tekent het formulier opnieuw zodra de categorie of een kenmerk
  // verandert, en gooit daarbij velden leeg die we al hadden gevuld — daardoor
  // kwamen beschrijving en kleur soms leeg door terwijl de stap zelf "ok"
  // meldde. In plaats van te raden wélke stap dat was, meten we aan het einde
  // gewoon na wat er écht in het formulier staat en vullen we opnieuw aan.
  //
  // Deze ronde heeft een tijdslot. Elk herstel is zelf al een reeks pogingen, en
  // drie rondes van alles konden samen de hele beschikbare tijd opsouperen —
  // dan stond het formulier keurig gevuld op het scherm maar werd er nooit meer
  // geplaatst. Vullen wat kan, en op tijd doorgaan naar Plaatsen.
  async function repairEmptyFieldsVinted(item, wantTitle) {
    const deadline = Date.now() + 45000;
    let kleurHersteld = 0;
    for (let round = 0; round < 3; round++) {
      if (Date.now() > deadline) {
        clog("eindcontrole: tijd op, door naar plaatsen");
        return false;
      }
      const titleEl = qs('input[data-testid="title--input"]');
      const descEl  = qs('textarea[data-testid="description--input"]');
      const priceEl = qs('input[data-testid="price-input--input"]');
      const sizeEl  = qs('input[data-testid="category-size-single-grid-input"]');
      const colEl   = qs('input[data-testid="color-select-dropdown-input"]');

      const missing = [];
      if (titleEl && titleEl.value !== wantTitle) missing.push("title");
      if (descEl && !(descEl.value || "").trim() && item.description) missing.push("description");
      // Ook een prijs die er wél staat maar die Vinted afkeurt telt als "leeg" —
      // dat is precies het geval waarin het veld €39.99 toonde en het formulier
      // toch bleef klagen dat de prijs minstens 1,0 moet zijn.
      if (priceEl && (!(_num(priceEl.value) >= 1) || priceErrorVinted())) missing.push("price");
      if (sizeEl && !(sizeEl.value || "").trim() && item.size) missing.push("size");
      if (colEl && !(colEl.value || "").trim()) missing.push("colour");
      if (!missing.length) return true;

      console.warn("[Omnivaleur] Vinted eindcontrole ronde " + (round + 1) + ", nog leeg:", missing.join(", "));
      for (const field of missing) {
        if (field === "title") fillInput(titleEl, wantTitle);
        if (field === "description") {
          await step("description (herstel)", () =>
            fillDescription(['textarea[data-testid="description--input"]'], item.description));
        }
        if (field === "price") await step("price (herstel)", () => fillPriceVinted(item.price));
        if (field === "size") await step("size (herstel)", () => fillAttributeVinted(["size"], String(item.size)));
        // Kleur maar één keer opnieuw proberen. Lukt het dan niet, dan lukt het
        // in ronde drie ook niet en kost het alleen de tijd die we nodig hebben
        // om te plaatsen.
        if (field === "colour" && kleurHersteld++ === 0) {
          await step("colour (herstel)", () => fillColourVinted(item));
        }
        await sleep(400);
      }
    }
    return false;
  }

  // Parse a displayed price ("€12,50", "12.50", "") to a Number (NaN if none).
  function _num(v) {
    const s = String(v ?? "").replace(/[^\d.,]/g, "").replace(",", ".");
    const n = parseFloat(s);
    return isFinite(n) ? n : NaN;
  }

  function priceErrorVinted() {
    const el = qs('input[data-testid="price-input--input"]');
    const zichtbaar = (e) => e && e.offsetParent !== null && (e.textContent || "").trim();
    const kandidaten = [];
    if (el) {
      for (const id of (el.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean)) {
        const e = document.getElementById(id);
        if (e) kandidaten.push(e);
      }
      let n = el.parentElement;
      for (let i = 0; i < 4 && n; i++, n = n.parentElement) kandidaten.push(...n.querySelectorAll("*"));
    }
    kandidaten.push(...document.querySelectorAll('[class*="validation"], [class*="Validation"], [role="alert"], [class*="error" i]'));
    const hit = kandidaten.find(e => zichtbaar(e) && PRICE_ERR_RE.test(e.textContent));
    return hit ? hit.textContent.trim().slice(0, 140) : null;
  }

  // Wacht kort af of die melding alsnog opduikt. Zonder deze pauze keurde de
  // extensie een prijs goed die Vinted een tel later afwees.
  async function priceErrorAfterSettle(ms = 1200) {
    const tot = Date.now() + ms;
    do {
      const err = priceErrorVinted();
      if (err) return err;
      await sleep(200);
    } while (Date.now() < tot);
    return null;
  }

  // ---- PRICE: Vinted expects a plain number with a DOT (or no decimals). ----
  // Vinted's price field is a masked/React-controlled input, so a bare
  // native-setter + "input" event often gets discarded and the field stays €0.
  // We type it properly: focus → select-all → clear → set → and if that didn't
  // stick, fall back to execCommand("insertText") (the same pipeline real typing
  // uses, which masked inputs honour). Returns true only if the field ends up
  // holding a valid (>= 1) price. Async so callers can await the verification.
  async function fillPriceVinted(price) {
    const el = qs('input[data-testid="price-input--input"]');
    if (!el) return false;
    const num = _num(price);
    if (!isFinite(num) || num < 1) return false;

    const fixed = num.toFixed(2);
    const comma = fixed.replace(".", ",");
    // Beide schrijfwijzen meesturen; de volgorde is nog steeds een gok op basis
    // van de taal, maar welke Vinted écht accepteert wordt nu bepaald door of
    // hij erover klaagt — niet door onze gok.
    const nlFirst = _vintedLocaleIsComma(el);
    const variants = Number.isInteger(num)
      ? [String(num), num.toFixed(2).replace(".", ","), num.toFixed(2)]
      : (nlFirst ? [comma, fixed] : [fixed, comma]);

    // Eerst de enige route die het formulier écht binnenkomt: zetten vanuit de
    // pagina zelf, met React's waarde-tracker gereset. Vanuit dit script (een
    // aparte wereld) is die tracker onzichtbaar, en dan toont het veld wel de
    // prijs maar houdt Vinted vast aan zijn lege interne waarde — de melding
    // "Price must be greater than or equal to 1.0" bij een ingevulde €14,99.
    try {
      const res = await new Promise((resolve) => {
        chrome.runtime.sendMessage(
          { type: "SET_PRICE_MAIN", selector: 'input[data-testid="price-input--input"]', values: variants },
          (r) => resolve(r || null),
        );
      });
      // De hoofdwereld heeft zelf al op de klacht gewacht; hier nog een korte
      // tweede blik, want de melding kan ook buiten het blokje rond het veld
      // opduiken.
      if (res && res.ok && !(await priceErrorAfterSettle(1500))) {
        clog(`prijs gezet via de pagina zelf: ${res.used}`);
        return true;
      }
      if (res && !res.ok) clog(`prijs via de pagina zelf lukte niet (${res.reason || "?"}) — nu de gewone route`);
    } catch (e) {
      clog(`prijs via de pagina zelf niet beschikbaar: ${e?.message || e}`);
    }

    // Integers need no separator; only the fractional variants differ by locale.
    if (Number.isInteger(num)) return await _typePriceVariant(el, String(num), num);

    // Locale-aware separator: Vinted's NL mask wants a COMMA ("34,99"); a DOT
    // makes the mask drop the fraction → the field reads as invalid ("≥ 1.0").
    // Prefer the variant matching the detected locale, then try the other. We
    // VERIFY each attempt sticks (value + no validation error) before accepting.
    for (const out of variants) {
      if (await _typePriceVariant(el, out, num)) return true;
    }
    // Derde poging: teken voor teken typen, met echte toetsaanslagen. Een
    // gemaskeerd invoerveld negeert soms een waarde die er in één keer in wordt
    // gezet (het veld toont dan €39.99 terwijl het formulier "moet ≥ 1,0" blijft
    // roepen), maar volgt losse aanslagen wél.
    for (const out of variants) {
      if (await _typePriceVariant(el, out, num, { perChar: true })) return true;
    }

    // VIERDE EN BESLISSENDE POGING (31-08-2026).
    //
    // Alle routes hierboven zetten de prijs opnieuw. Als het veld de prijs al
    // TOONT en Vinted tóch klaagt, is dat niet het probleem: het formulier houdt
    // dan een eigen, lege waarde vast naast wat er op het scherm staat. Daniel
    // vond de handeling die dat wél oplost, en die is verrassend klein: hij
    // vervangt met de hand één teken door hetzelfde teken ("een 9 door mijn
    // eigen 9"), en daarna gaat publiceren gewoon door.
    //
    // Dat doen we hier na, met de bewerkroute van de browser zelf in plaats van
    // met verzonnen gebeurtenissen — dus dezelfde weg als een toetsaanslag.
    if (Math.abs((_num(el.value) || -1) - num) < 0.01) {
      for (let poging = 0; poging < 2; poging++) {
        if (await _hertypLaatsteTeken(el, num)) return true;
      }
    }
    return false;
  }

  // Eén teken weghalen en meteen opnieuw typen, zonder de prijs te veranderen.
  // Zie de vierde poging in fillPriceVinted: dit is de handeling waarvan op het
  // echte formulier is vastgesteld dat hij de klacht wegneemt. Goedkeuren doen
  // we alleen als de prijs daarna nog steeds klopt én de rode regel weg is.
  async function _hertypLaatsteTeken(el, num) {
    const huidig = String(el.value || "");
    if (!huidig) return false;
    const laatste = huidig.slice(-1);
    el.focus();
    el.dispatchEvent(new Event("focus", { bubbles: true }));

    // Eerst het laatste teken selecteren en over zichzelf heen typen. Lukt die
    // selectie niet (een gemaskeerd veld staat dat niet altijd toe), dan wissen
    // we het teken en typen het opnieuw — hetzelfde eindresultaat.
    let gelukt = false;
    try { el.setSelectionRange(huidig.length - 1, huidig.length); } catch (e) {}
    try { gelukt = document.execCommand("insertText", false, laatste); } catch (e) { gelukt = false; }
    if (!gelukt || String(el.value || "") !== huidig) {
      try { el.setSelectionRange(huidig.length, huidig.length); } catch (e) {}
      try { document.execCommand("delete", false, null); } catch (e) {}
      await sleep(80);
      try { document.execCommand("insertText", false, laatste); } catch (e) {}
    }
    await sleep(150);
    el.dispatchEvent(new Event("change", { bubbles: true }));
    el.dispatchEvent(new Event("blur", { bubbles: true }));

    const got = _num(el.value);
    if (!isFinite(got) || Math.abs(got - num) >= 0.01) {
      clog(`hertypen veranderde de prijs (${el.value}) — niet geaccepteerd`);
      return false;
    }
    const err = await priceErrorAfterSettle(900);
    if (err) {
      clog(`hertypen hielp niet, Vinted klaagt nog steeds: ${err}`);
      return false;
    }
    clog("prijs geaccepteerd na het opnieuw typen van het laatste teken");
    return true;
  }

  // True if the page/input locale uses a comma decimal separator (NL etc.).
  function _vintedLocaleIsComma(el) {
    // HET VELD ZELF GAAT VOOR. Vinted zet de verwachte schrijfwijze letterlijk in
    // de placeholder ("€0.00" of "€0,00"); dat is geen gok maar het antwoord.
    //
    // Live gemeten op 26-08-2026 op vinted.nl: lang="en-NL" (Engels ingesteld op
    // de Nederlandse markt) en placeholder "€0.00" — het veld wil dus een PUNT.
    // De taal zei iets anders: navigator.language is daar "nl-NL", en op die
    // terugval koos de oude volgorde de komma. Wat dat oplevert is niet "iets
    // minder mooi" maar kapot: "4,99" maakt er "€NaN" van.
    const hint = (el.getAttribute("placeholder") || el.value || "").trim();
    if (hint.includes(",")) return true;
    if (hint.includes(".")) return false;
    // Geen aanwijzing in het veld? Dan pas de taal, en dan liefst die van de
    // pagina zelf — navigator.language is de instelling van de bróswer, niet van
    // het formulier, en juist die twee liepen hier uiteen.
    const lang = (document.documentElement.getAttribute("lang") || navigator.language || "").toLowerCase();
    return /^(nl|de|fr|es|it|pt|pl)/.test(lang);
  }

  // Type one formatted value into the masked price input and verify it holds the
  // intended number with no visible "must be ≥" / invalid error. Returns true only
  // then — leaving whichever separator worked in the field.
  async function _typePriceVariant(el, out, num, opts = {}) {
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
    const clear = () => {
      el.focus();
      try { el.select(); } catch (e) {}
      try { setter.call(el, ""); } catch (e) { el.value = ""; }
      el.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "deleteContentBackward" }));
    };

    el.dispatchEvent(new Event("focus", { bubbles: true }));
    clear();

    if (opts.perChar) {
      // Zo dicht mogelijk bij echt typen: per teken keydown → invoer → keyup.
      for (const ch of out) {
        el.dispatchEvent(new KeyboardEvent("keydown", { key: ch, bubbles: true }));
        let typed = false;
        try { typed = document.execCommand("insertText", false, ch); } catch (e) { typed = false; }
        if (!typed) {
          try { setter.call(el, (el.value || "") + ch); } catch (e) { el.value = (el.value || "") + ch; }
          el.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: ch }));
        }
        el.dispatchEvent(new KeyboardEvent("keyup", { key: ch, bubbles: true }));
        await sleep(60);
      }
      el.dispatchEvent(new Event("change", { bubbles: true }));
      await sleep(120);
    } else {
      // Programmatic set + input/change.
      try { setter.call(el, out); } catch (e) { el.value = out; }
      el.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: out }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
      await sleep(120);

      // If the masked input rejected the programmatic value, retry via real typing.
      if (Math.abs((_num(el.value) || -1) - num) >= 0.01) {
        el.focus();
        try { el.select(); } catch (e) {}
        try { document.execCommand("selectAll", false, null); } catch (e) {}
        try { document.execCommand("insertText", false, out); } catch (e) {}
        el.dispatchEvent(new Event("change", { bubbles: true }));
        await sleep(120);
      }
    }
    el.dispatchEvent(new Event("blur", { bubbles: true }));
    await sleep(150);

    // Verify: field parses to the intended number AND isn't flagged invalid.
    const got = _num(el.value);
    if (!isFinite(got) || Math.abs(got - num) >= 0.01) return false;
    if (el.getAttribute("aria-invalid") === "true") return false;
    // En pas goedkeuren als de rode melding ook na een korte pauze wegblijft:
    // Vinted zet hem soms een halve seconde later neer, en dan stond hij er nog
    // gewoon op het moment van plaatsen.
    const err = await priceErrorAfterSettle(900);
    if (err) {
      clog(`prijs "${out}" werd geweigerd door Vinted: ${err}`);
      return false;
    }
    return true;
  }

  // ---- CATEGORY: prefer Vinted's own "Suggested" options, then verify the match. ----

  function vintedPathFor(cat, gender) {
    const isHeren = gender === "heren" || gender === "men";
    const isDames = gender === "dames" || gender === "women";
    if (!isHeren && !isDames) return null;   // kinderen/unisex: via zoeken
    const tak = isHeren ? "heren" : "dames";
    // "heren wielrenkleding" → "wielrenkleding"
    const kaal = cat.replace(/^(heren|dames)\s+/, "");
    const rest = V_KLEDING[tak][kaal];
    if (!rest) return null;
    return [isHeren ? "Men" : "Women", "Clothing", ...rest];
  }

  // BLAD_VOORKEUR en enkelvoud stonden hier, en dat brak het publiceren.
  // Ze staan nu bovenaan, bij de andere hulpwaarden — zie de toelichting daar.

  function kiesBlad(namen, tekst) {
    // 1. Een voorkeurswoord in de tekst dat één op één bij een blad hoort.
    for (const [inTekst, inNaam] of BLAD_VOORKEUR) {
      if (!inTekst.test(tekst)) continue;
      const i = namen.findIndex((n) => inNaam.test(n));
      if (i >= 0) return i;
    }
    // 2. Anders: het blad waarvan de meeste eigen woorden in de tekst staan.
    //    Woorden die in élk blad terugkomen ("shirts" onder Shirts) zeggen
    //    niets en tellen daarom niet mee.
    const alleWoorden = namen.map((n) =>
      n.toLowerCase().replace(/&/g, " ").split(/[^a-z0-9-]+/).filter((w) => w.length > 3).map(enkelvoud));
    // HET VANGBLAD MAG NIET MEETELLEN BIJ HET TELLEN (31-08-2026).
    //
    // "Other jumpers & sweaters" herhaalt per definitie de woorden van zijn
    // buren. Telde dat blad mee, dan was "jumper" ineens géén eigen woord meer
    // van "Jumpers" — het kwam immers twee keer voor — en scoorde geen enkel
    // blad iets. Daarna viel de keuze op stap 3, en dat is nu juist datzelfde
    // "Other …". Gevolg: (1356) Beige Suitsupply Jumper belandde onder "Other
    // jumpers & sweaters" terwijl "Jumpers" er letterlijk in de titel stond.
    //
    // Dit blad wordt hieronder toch al overgeslagen bij het scoren; het hoort
    // dus ook niet mee te tellen bij het bepalen wat een eigen woord is.
    const telling = {};
    for (let i = 0; i < alleWoorden.length; i++) {
      if (/^other\b/i.test(namen[i])) continue;
      for (const w of new Set(alleWoorden[i])) telling[w] = (telling[w] || 0) + 1;
    }
    const woordenTekst = new Set(tekst.replace(/&/g, " ").split(/[^a-z0-9-]+/).map(enkelvoud));
    let beste = -1, besteScore = 0;
    alleWoorden.forEach((ws, i) => {
      if (/^other\b/i.test(namen[i])) return;
      const score = ws.filter((w) => telling[w] === 1 && woordenTekst.has(w)).length;
      if (score > besteScore) { besteScore = score; beste = i; }
    });
    if (beste >= 0) return beste;
    // 3. Zegt het artikel niets over model of pasvorm, kies dan het meest
    //    neutrale blad. Zonder deze regel viel de keuze op de éérste optie, en
    //    dat is bij spijkerbroeken "Ripped jeans" — dan staat een gave broek te
    //    koop als kapotte broek. Live nagelopen op vinted.nl.
    const n = namen.findIndex((t) => /^(other|straight|regular|classic|basic)\b/i.test(t));
    return n >= 0 ? n : (namen.length ? 0 : null);
  }

  // Loopt het pad af in Vinted's kiezer. Stopt zodra de lijst dichtklapt en het
  // veld een waarde heeft — dat is Vinted's eigen signaal dat de categorie
  // gekozen is. Zijn er onderweg nog subcategorieën, dan kiest hij het blad dat
  // in de titel/beschrijving voorkomt, anders het neutrale "Other …", anders de
  // eerste. Zo wordt er nooit een eigenschap verzonnen die er niet is.
  async function walkVintedCategoryPath(item, cat, gender) {
    const pad = vintedPathFor(cat, gender);
    if (!pad) return false;
    const inp = qs('input[data-testid="catalog-select-dropdown-input"]');
    if (!inp) return false;
    const cellen = () => [...document.querySelectorAll('[class*="Cell__clickable"]')]
      .filter((e) => e.offsetParent !== null);
    const titel = (e) =>
      (e.querySelector('[class*="Cell__title"]')?.textContent || e.textContent || "").trim();
    const klik = async (label) => {
      const c = cellen().find((e) => titel(e).toLowerCase() === label.toLowerCase());
      if (!c) return false;
      realClickEl(c);
      await sleep(1100);
      return true;
    };

    if (!cellen().length) {
      inp.scrollIntoView({ block: "center" });
      await sleep(200);
      realClickEl(inp);
      await sleep(1200);
    }
    if (!cellen().length) return false;

    for (const stap of pad) {
      if (!(await klik(stap))) {
        clog(`Vinted-categorie: stap "${stap}" niet gevonden — terug naar zoeken`);
        return false;
      }
    }

    // Nog dieper? Dan zelf een verstandig blad kiezen (max 3 niveaus).
    const tekst = `${item.title || ""} ${item.description || ""}`.toLowerCase();
    for (let i = 0; i < 3 && cellen().length; i++) {
      const opties = cellen();
      const keuze = kiesBlad(opties.map(titel), tekst) != null
        ? opties[kiesBlad(opties.map(titel), tekst)] : opties[0];
      clog(`Vinted-categorie: extra niveau → "${titel(keuze)}"`);
      realClickEl(keuze);
      await sleep(1100);
    }

    const gekozen = (inp.value || "").trim();
    if (gekozen) {
      clog(`Vinted-categorie via de boom: ${pad.join(" > ")} → "${gekozen}"`);
      return true;
    }
    clog("Vinted-categorie: boom afgelopen maar niets vastgelegd — terug naar zoeken");
    return false;
  }

  async function fillCategoryVinted(item) {
    const cat = (item.category || "").toLowerCase().trim();
    const gender = (item.gender || "").toLowerCase().trim(); // "heren"/"dames" if present
    const inp = qs('input[data-testid="catalog-select-dropdown-input"]');
    if (!inp) return false;

    // Eerst het zekere pad: klik Vinted's eigen categorieboom af. Zoeken +
    // punten toekennen blijft daarna als terugval bestaan, maar is een loterij —
    // op de zoekresultaten voor "jeans" bestaat namelijk geen gewone "Jeans",
    // alleen "Ripped/Skinny/Slim fit/Straight fit", en dan won de kortste naam.
    // Zo stond een doodgewone spijkerbroek te koop als kapotte spijkerbroek.
    if (await walkVintedCategoryPath(item, cat, gender)) return true;

    let hints = (CAT_HINTS[gender ? `${gender} ${cat}` : cat] || CAT_HINTS[cat] || [])
      .map((h) => h.toLowerCase());

    // The dashboard offers ONE flat "Accessories" option per gender, but Vinted
    // splits accessories into separate leaves (Watches, Belts, Scarves, Hats,
    // Jewellery, Bags, Wallets…). So the category alone can't say which one — the
    // stock hints for "accessoires" are just ["bags","scarves","jewellery",
    // "accessories"], which is why a watch landed in the wrong leaf or nowhere at
    // all. Read the noun out of the item's own title and lead with that.
    if (/accessoire|accessor/.test(cat)) {
      const text = `${item.title || ""} ${item.description || ""}`.toLowerCase();
      const specific = ACCESSORY_TERMS.find(([re]) => re.test(text));
      if (specific) hints = [...specific[1], ...hints];
    }
    // For relisted imports the category is captured straight from Vinted's own
    // breadcrumb (e.g. "Jumpers & sweaters"), which won't be in CAT_HINTS — use
    // that raw text as a hint so we can still filter the catalogue to it.
    if (!hints.length && cat) hints.push(cat);
    const wantMen = gender === "heren" || gender === "men";
    const wantWomen = gender === "dames" || gender === "women";

    inp.focus();
    inp.click();
    await sleep(700);

    const visible = (el) => !!el && (el.offsetParent !== null || el.getClientRects().length > 0);

    // Type into the catalogue SEARCH without blurring. fillInput() dispatches a
    // "blur" that closes Vinted's dropdown, wiping the typed results before we
    // can read them — fatal for every non-suggested category (games, electronics,
    // any leaf that needs searching). Here we set the value + fire input/keyup and
    // KEEP focus so the result list stays open.
    //
    // LET OP: het veld dat je ziet staan ("Select a category") is NIET het
    // zoekveld. Zodra de lijst opengaat verschijnt daarbinnen een eigen zoekvak
    // ("Find a category"), en alleen dáármee filtert Vinted zijn categorieboom.
    // Al het getypte in het bovenste veld werd domweg genegeerd: de lijst bleef
    // op "Women / Men / Kids / …" staan. Daardoor kon de extensie in de praktijk
    // alleen kiezen uit wat Vinted zelf toevallig voorstelde, en viel elke
    // categorie die je moet zóéken buiten de boot. Live nagelopen op vinted.nl.
    const searchBox = () => {
      const inputs = [...document.querySelectorAll('input[type="text"], input:not([type])')]
        .filter((e) => e.offsetParent !== null && e !== inp);
      return inputs.find((e) => /find a category|zoek een categorie|categorie/i.test(e.placeholder || ""))
        || inputs.find((e) => /InputBar/.test(e.className || ""))
        || inp;  // terugval: beter iets typen dan niets
    };
    const typeSearch = (value) => {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
      const box = searchBox();
      box.focus();
      try { setter.call(box, ""); } catch (_) { box.value = ""; }
      box.dispatchEvent(new Event("input", { bubbles: true }));
      try { setter.call(box, value); } catch (_) { box.value = value; }
      box.dispatchEvent(new Event("input", { bubbles: true }));
      box.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true, key: value.slice(-1) }));
    };

    // Collect the suggested option rows. Vinted hides the native radio (custom-styled),
    // so we must NOT filter on radio visibility — we filter on the visible ROW instead.
    // Strategy A: every radio/role=radio → its clickable row. Strategy B (fallback):
    // find rows by their breadcrumb text ("Men > Shoes") when no radios are exposed.
    const rowSel = 'label, li, [role="option"], [role="radio"], [class*="Cell"], [class*="option"], [class*="Suggestion"]';
    const collectChoices = () => {
      const out = [];
      const seen = new Set();
      // De naam van de categorie en het kruimelpad zitten in twee losse blokjes
      // die in de platte tekst aan elkaar plakken: "Team shirts & jerseysWomen >
      // Clothing > Activewear". Daardoor herkende \bwomen\b het woord "Women"
      // niet (het zit vast aan "jerseys"), viel de hele man/vrouw-weging weg en
      // kon een herenartikel zomaar in de damescategorie belanden. We zetten er
      // dus een scheiding tussen. Live vastgesteld op vinted.nl.
      const rowText = (row) => {
        const titel = row.querySelector?.('[class*="Cell__title"]')?.textContent || "";
        const pad = row.querySelector?.('[class*="Cell__body"]')?.textContent || "";
        const ruw = (titel && pad) ? `${titel} | ${pad}` : (row.textContent || "");
        return ruw
          .replace(/([a-z0-9&\]])([A-Z])/g, "$1 $2")  // "jerseysWomen" → "jerseys Women"
          .replace(/\s+/g, " ")
          .trim()
          .toLowerCase();
      };
      const push = (radio, row) => {
        if (!row || seen.has(row) || !visible(row)) return;
        const text = rowText(row);
        if (text.length <= 2 || text.length > 200) return;
        seen.add(row);
        out.push({ radio, row, text });
      };
      // A: anchored on radios (even if the input itself is visually hidden).
      for (const r of document.querySelectorAll('input[type="radio"], [role="radio"]')) {
        push(r.matches('input[type="radio"]') ? r : null, r.closest(rowSel) || r.parentElement);
      }
      // B: anchored on the breadcrumb subtitle inside Vinted's web_ui Cell component.
      // The breadcrumb lives in `.web_ui__Cell__body`; the clickable row is the
      // enclosing `.web_ui__Cell` and the (hidden) radio sits in its suffix.
      if (!out.length) {
        const bc = /\b(men|women|kids|unisex)\b\s*[>›\/]/i;
        const bodies = document.querySelectorAll(
          '[class*="Cell__body"], [class*="Cell__title"], [class*="Cell__heading"]');
        const pool = bodies.length ? bodies : document.querySelectorAll("div, li, label, span, button, a");
        for (const e of pool) {
          if (!bc.test(e.textContent || "")) continue;
          if ([...e.children].some((ch) => bc.test(ch.textContent || ""))) continue; // smallest match
          const row = e.closest('[class*="Cell__cell"], [class*="web_ui__Cell"]')
            || e.closest('label, li, [role="option"], [role="radio"]') || e;
          push(row.querySelector?.('input[type="radio"]') || null, row);
        }
      }
      // C: generic fallback for ANY category (games, electronics, etc.). When we
      // type into the search, Vinted renders leaf results as plain rows inside a
      // dropdown/listbox with NO gender breadcrumb — Strategy B skips those. Here
      // we harvest every visible option row from the open menu regardless of its
      // breadcrumb, so non-clothing categories get real candidates to score.
      // Gated on an active search term: without it the initial click shows the
      // top-level category TREE ("Women", "Men", …) and harvesting those could
      // commit a bare parent category — we only trust C once we've searched.
      if (!out.length && inp.value.trim().length > 0) {
        const menus = document.querySelectorAll(
          '[role="listbox"], [class*="dropdown"], [class*="Dropdown"], [class*="Menu"], [class*="menu"], [data-testid*="dropdown"]');
        const rows = [];
        (menus.length ? menus : [document]).forEach((m) =>
          rows.push(...m.querySelectorAll('[role="option"], li, label, [class*="Cell"], [class*="option"], [class*="Suggestion"]')));
        for (const row of rows) {
          push(row.querySelector?.('input[type="radio"]') || null, row);
        }
      }
      return out;
    };

    // Niche sport-shoe categories Vinted often suggests for a plain sneaker. We only
    // want these when the listing itself names that sport — otherwise a normal shoe
    // gets buried in e.g. "Tennis shoes" just because it tied on the generic "shoes".
    const NICHE_SHOE = ["tennis", "football", "running", "basketball", "hiking",
      "golf", "cycling", "skate", "boxing", "wrestling", "climbing"];
    const itemText = `${item.title || ""} ${item.description || ""}`.toLowerCase();

    // WELKE TAK IS DIT ARTIKEL SOWIESO NIET?
    //
    // Het dashboard groepeert zijn categorieën per tak, en die tak staat vooraan
    // in de sleutel: "antiek lampen", "wonen tafellampen", "kunst beelden en
    // houtsnijwerken", "muziek gitaren", "sieraden ringen", "games …",
    // "electronics …", "audio …". Niets daarvan is kleding, en dus mag zo'n
    // artikel NOOIT in een kledingblad van Vinted belanden.
    //
    // Amanda, 30-08-2026: "Bij het plaatsen op Vinted, wil hij alles in de
    // categorie kinderkleding gooien". Haar voorraad is brocante: lampen,
    // beeldjes, servies, rozenkransen. Bij zo'n artikel raakt geen enkele hint
    // een kledingblad — maar een blad dat "Other …" heet kreeg hieronder tóch
    // een bonuspunt, en één punt is genoeg om gekozen te worden. Zo won
    // "Other children's clothing" van niets.
    const NIET_KLEDING_TAK = /^(wonen|antiek|kunst|muziek|sieraden|games|electronics|audio)\b/;
    const isNietKleding = NIET_KLEDING_TAK.test(cat);

    // Gaat het om een kledingstuk? Alleen dan gelden de uitsluitingen hieronder.
    // Schoen-, sieraden-, games- en elektronicacategorieën moeten juist wél in
    // hun eigen tak terechtkomen.
    const isClothingCat = !!cat
      && !isNietKleding
      && !/schoen|sneaker|laarzen|hakken|sandalen|boots|shoes|trainers/.test(cat)
      && !/accessoire|accessor/.test(cat);

    // Does the listing (title/description) OR the dashboard category actually name
    // this sport? Only then is a niche sport-shoe category the right pick.
    const hintText = hints.join(" ");
    const sportNamed = (n) => itemText.includes(n) || hintText.includes(n);

    // Score a choice on category hints (+3 each) and gender breadcrumb (+/-).
    // Returns -Infinity to HARD-exclude a row (niche sport shoe on a plain sneaker).
    const score = (c) => {
      const t = c.text;
      // Kleding hoort nooit bij schoenen of bij sportMATERIAAL. Vinted zet onder
      // "Sports" de spullen (fietsen, ski's, ballen) en heeft daarnaast losse
      // schoenbladen als "Cycling shoes". Een wielrenshirt scoorde daar juist
      // hoog op, omdat het woord "cycling" klopte — en belandde dus bij de
      // fietsonderdelen in plaats van bij de kleding. Live gezien op vinted.nl.
      if (isClothingCat) {
        if (/\bshoes?\b|\bboots\b|\btrainers\b|\bsneakers\b/.test(t)) return -Infinity;
        if (/(^|[\s>›])sports\s*[>›]/.test(t)) return -Infinity;
        if (/\bequipment\b|\bhelmets?\b|\bbikes?\b|\bballs?\b|\baccessories\b.*\bsports\b/.test(t)) return -Infinity;
      }
      // Hard exclude a niche sport-shoe suggestion unless the sport is actually named.
      // A -4 penalty wasn't enough: on ties or weak hints "Tennis shoes" could still
      // surface. A normal sneaker must NEVER land in Tennis/Football/Running shoes.
      for (const n of NICHE_SHOE) if (t.includes(n) && !sportNamed(n)) return -Infinity;
      // Een lamp, een beeldje of een rozenkrans hoort nergens onder "Kleding".
      // Vinted noemt die tak in het Engels "Clothing" en in het Nederlands
      // "Kleding"; beide vormen komen in het kruimelpad voor.
      if (isNietKleding && /\bclothing\b|\bkleding\b/.test(t)) return -Infinity;
      let s = 0;
      // Raakt dit blad überhaupt iets van wat we zoeken?
      let geraakt = false;
      // De naam van de categorie zelf weegt zwaarder dan het pad ernaartoe.
      // Anders telde een woord dubbel — één keer als bladnaam en één keer in het
      // kruimelpad — en won "Activewear > Tops & t-shirts" van het gewone
      // "Tops & t-shirts > T-shirts" voor een doodgewoon T-shirt.
      const [blad, pad] = t.includes(" | ") ? t.split(" | ") : [t, ""];
      for (const h of hints) {
        if (blad.includes(h)) { s += 3; geraakt = true; }
        else if (pad.includes(h)) { s += 2; geraakt = true; }
      }
      // Sportkleding zit bij Vinted in een eigen tak ("Activewear"). Hoort het
      // artikel daar niet, dan mag het daar ook niet belanden — en andersom.
      const sportTak = /\bactivewear\b/.test(t);
      const wilSport = hints.includes("activewear");
      if (wilSport && !sportTak) s -= 3;
      if (!wilSport && sportTak) s -= 6;
      // Vinted splitst veel categorieën verder uit naar een eigenschap:
      // "Ripped jeans", "Puffer jackets", "Checked shirts". Bij gelijke score won
      // zo'n blad het van de gewone categorie (kortste tekst), en dan stond een
      // doodgewone spijkerbroek te koop als kapotte spijkerbroek. Zo'n bijvoeglijk
      // blad mag alleen winnen als het artikel dat woord zélf noemt.
      const KWALIFICATIES = /\b(ripped|skinny|bootcut|flared|straight|mom|dad|boyfriend|cargo|puffer|parka|trench|bomber|windbreaker|raincoat|down|fur|faux|leather|denim|checked|striped|print|plain|graphic|floral|sleeveless|cropped|oversized|knitted|quilted|hooded)\b/g;
      for (const woord of (blad.match(KWALIFICATIES) || [])) {
        if (!itemText.includes(woord) && !hints.some((h) => h.includes(woord))) s -= 4;
      }
      // Het neutrale verzamelblad ("Other jeans") is bij twijfel juist goed:
      // het is de categorie zonder aanname over model of stof.
      if (/^other\b/.test(blad)) s += 1;
      // Explicitly favour the plain footwear buckets for ordinary shoes.
      if (/\b(sneakers|trainers)\b/.test(t)) s += 2;
      const isMenRow = /\bmen\b/.test(t) && !/women/.test(t);
      const isWomenRow = /\bwomen\b/.test(t);
      if (wantMen) { if (isMenRow) s += 3; if (isWomenRow) s -= 5; }
      if (wantWomen) { if (isWomenRow) s += 3; if (isMenRow) s -= 5; }
      if (hints.length === 0 && /shoe|clothing|jacket|dress|jeans/.test(t)) { s += 1; geraakt = true; }
      // EEN BONUSPUNT MAG NOOIT DE KEUZE MAKEN.
      //
      // Alles hierboven ("Other …" is +1, sneakers is +2, de juiste sekse is +3)
      // is bedoeld om te kiezen TUSSEN bladen die al ergens op sloegen. Maar
      // `best()` neemt elk blad met een score boven nul, dus zo'n bonuspunt was
      // in zijn eentje genoeg. Bij een artikel waar geen enkele hint op past —
      // een vintage lamp, een beeldje, een rozenkrans — won daardoor het eerste
      // blad dat toevallig "Other …" heette of het woord "sneakers" droeg. Dat
      // is precies hoe brocante bij de kinderkleding belandde.
      //
      // Raakt een blad geen enkele hint, dan is het geen kandidaat. Liever geen
      // categorie (de verkoper kiest zelf) dan de verkeerde.
      if (!geraakt) return 0;
      return s;
    };

    const realClick = realClickEl;

    const commit = async (c) => {
      // Vinted's custom radio reacts to a full pointer sequence on the row/label,
      // not to a bare .click() of the hidden input. Try row, label, then radio.
      const label = c.radio?.id ? document.querySelector(`label[for="${c.radio.id}"]`) : null;
      realClick(c.row);
      await sleep(150);
      if (c.radio && !c.radio.checked && label) { realClick(label); await sleep(150); }
      if (c.radio && !c.radio.checked) { c.radio.click(); await sleep(150); }
      await sleep(400);
      // Some flows need a leaf "Select"/confirm step.
      const confirm = [...document.querySelectorAll('button, [role="option"]')]
        .find((b) => b.offsetParent !== null && /^(select|kies|done|opslaan|save)$/i.test(b.textContent.trim()));
      if (confirm) { confirm.click(); await sleep(300); }
    };

    const best = (choices) => {
      const scored = choices.map((c) => ({ c, s: score(c) })).filter((x) => x.s > 0)
        // Tiebreak on the SHORTER row text: the leaf ("Men › Jeans") beats a broad
        // parent, and avoids picking an over-long noisy row on an equal score.
        .sort((a, b) => (b.s - a.s) || (a.c.text.length - b.c.text.length));
      if (!scored.length) return null;
      // Ambiguity guard: only bail when the tie is a GENUINE gender clash — a
      // men-row tied with a women-row while the item has no gender. For everything
      // else (games, electronics, unisex, or a tie between same-gender leaves) the
      // tiebreak above is trustworthy, so we commit rather than skip the category.
      if (scored.length > 1 && scored[0].s === scored[1].s && !wantMen && !wantWomen) {
        const a = scored[0].c.text, b = scored[1].c.text;
        const genderClash =
          (/\bmen\b/.test(a) && !/women/.test(a) && /\bwomen\b/.test(b)) ||
          (/\bwomen\b/.test(a) && /\bmen\b/.test(b) && !/women/.test(b));
        if (genderClash) {
          console.warn("[Omnivaleur] Vinted category ambiguous (men vs women, no gender on item):",
            a, "vs", b, "— set item.gender to disambiguate.");
          return null;
        }
      }
      return scored[0].c;
    };

    // 1) Try the suggestions Vinted already shows — poll, they render async.
    let initial = [];
    const t1 = Date.now() + 8000; // image-recognition suggestions can take several seconds
    while (Date.now() < t1) {
      initial = collectChoices();
      if (initial.length) break;
      await sleep(250);
    }
    console.log("[Omnivaleur] Vinted category — gender:", gender || "(none)", "hints:", hints,
      "| found", initial.length, "options:", initial.map((c) => c.text.slice(0, 50)));
    let choice = best(initial);

    // 2) Otherwise type each hint in turn to filter the catalogue until one
    //    surfaces a usable option (the captured-category hint is tried too).
    if (!choice && hints.length) {
      for (const h of hints) {
        typeSearch(h);
        const deadline = Date.now() + 3500;
        while (Date.now() < deadline && !choice) {
          await sleep(250);
          choice = best(collectChoices());
        }
        if (choice) break;
      }
    }

    if (choice) {
      await commit(choice);
      return verifyCategory(hints, wantWomen);
    }
    return false;
  }

  // Confirm the committed category text actually reflects our item; warn if not.
  function verifyCategory(hints, wantWomen) {
    const display = (qs('input[data-testid="catalog-select-dropdown-input"]')?.value
      || document.querySelector('[data-testid="catalog-select-dropdown"]')?.textContent
      || "").toLowerCase();
    if (!display) return false;
    const hintOk = hints.length === 0 || hints.some((h) => display.includes(h));
    if (!hintOk) console.warn("[Omnivaleur] Vinted category may not match item:", display, "expected one of", hints);
    return hintOk;
  }

  // Like fillAttributeVinted but skips opening the trigger (panel already open).
  // ---- COLOUR: robust, verified multi-select (Vinted allows up to 2). ----
  // The old path silently failed when the colour didn't commit, leaving "Fill in
  // colour to continue". This version: normalises the value (string/array,
  // comma/slash/&/"en"-separated, Dutch→English), opens the panel, ticks each
  // colour's checkbox with fallbacks (input → label → row), scrolls options into
  // view like the material picker, and VERIFIES at least one colour is checked —
  // retrying the whole open+pick cycle before giving up.
  function parseColours(item) {
    let raw = item.color ?? item.colour ?? item.colours ?? item.colors ?? "";
    // Vangnet: staat er geen kleur bij het item, haal hem dan uit de titel
    // ("Black MyProtein Shorts"). Zonder dit sloeg de kleurstap meteen over en
    // bleef "Fill in colour to continue" staan.
    if (!String(raw).trim()) {
      const words = String(item.title || "").toLowerCase().split(/[^a-z]+/).filter(Boolean);
      const hit = words.find(w => COLOUR_MAP[w]);
      if (hit) raw = COLOUR_MAP[hit];
    }
    const list = Array.isArray(raw) ? raw : String(raw).split(/[,/;&]|\s+en\s+|\s+and\s+/i);
    const out = [];
    for (const s of list) {
      const v = String(s).trim();
      if (!v) continue;
      const mapped = COLOUR_MAP[v.toLowerCase()] || v;
      if (!out.some((o) => o.toLowerCase() === mapped.toLowerCase())) out.push(mapped);
      if (out.length === 2) break; // Vinted caps at 2 colours
    }
    return out;
  }

  // ---- Dropdown opener, verified against the live Vinted form ----
  // Two things were breaking every size/colour attempt:
  //  1. clicking a trigger that is scrolled out of view does nothing at all, and
  //  2. the panels no longer render `web_ui__Cell` rows with checkboxes.
  // So: always scroll the trigger into view first, then poll until the panel's
  // own options actually exist, retrying the click a few times.
  //
  // Let op de tijd: de hele opdracht heeft een paar minuten, en dit is een lus
  // in een lus. Te ruim wachten hier betekende dat het formulier wel netjes
  // gevuld werd maar de tijd op was vóór het plaatsen — het zoekertje bleef dan
  // ingevuld en ongeplaatst staan. Vandaar korte, harde grenzen.
  async function openDropdownVinted(trigger, isOpen, tries = 2) {
    if (!trigger) return false;
    for (let attempt = 0; attempt < tries; attempt++) {
      if (isOpen()) return true;
      trigger.scrollIntoView({ block: "center" });
      humanClickEl(trigger);
      if (await waitUntil(isOpen, 2500)) return true;
      // Het veld zelf reageert niet altijd: bij sommige velden zit de
      // klikafhandeling op de rij eromheen of op het pijltje ernaast. Pas
      // proberen als de directe klik niets deed, zodat we niets kapotmaken bij
      // velden waar hij wél werkt.
      for (const alt of [
        trigger.parentElement,
        trigger.closest('[class*="web_ui__Cell__cell"]'),
        trigger.parentElement?.querySelector('svg, [class*="chevron"], [class*="Chevron"], button'),
      ]) {
        if (!alt || alt === trigger) continue;
        humanClickEl(alt);
        if (await waitUntil(isOpen, 1200)) return true;
      }
    }
    return isOpen();
  }

  // ---- COLOUR ----
  // The colour picker is a grid of swatches: every option is a
  // [data-testid^="filter-grid-option-"] wrapper holding a [data-testid^="color_code_"]
  // bubble plus the colour's name as text. The chosen colour(s) land in the
  // trigger input's value ("Black"), which is what we verify against.
  // (COLOUR_TRIGGER_SEL en OTHER_TRIGGER_SEL staan bovenaan dit bestand — zie de
  // toelichting daar over declaraties die te laat bestaan.)

  // Waar de kleuropties kunnen staan: eerst de eigen paneelcontainer, anders de
  // dichtstbijzijnde voorouders van het kleurveld zelf (Vinted klapt het paneel
  // soms als accordeon ín het veld open, buiten die container om).
  function colourScopes() {
    const out = [];
    const content = document.querySelector('[data-testid="color-select-dropdown-content"]');
    if (content) out.push(content);
    const trigger = document.querySelector(COLOUR_TRIGGER_SEL);
    let n = trigger ? trigger.parentElement : null;
    for (let i = 0; n && i < 6; i++, n = n.parentElement) {
      if (n.querySelector(OTHER_TRIGGER_SEL)) break; // vanaf hier te ruim
      out.push(n);
    }
    return out;
  }

  // Vinted tekent de kleurkiezer in twee vormen: een raster met kleurbolletjes
  // ([data-testid^="filter-grid-option-"]) én — sinds kort, per categorie — een
  // lijst met web_ui__Cell-rijen en aanvinkvakjes. De oude code kende alleen het
  // raster, zag dus nul opties, concludeerde "paneel ging niet open" en liet de
  // kleur elke keer leeg. Nu herkennen we beide vormen.
  function colourOptionEls() {
    for (const scope of colourScopes()) {
      const grid = [...scope.querySelectorAll('[data-testid^="filter-grid-option-"]')]
        .filter((el) => el.querySelector('[data-testid^="color_code_"]'));
      if (grid.length) return grid;
      const cells = [...scope.querySelectorAll('[class*="web_ui__Cell__cell"]')]
        .filter((el) => el.querySelector('[class*="web_ui__Cell__title"]'));
      if (cells.length) return cells;
    }
    // Laatste vangnet: kleurbolletjes waar dan ook — die horen altijd bij kleur.
    return [...document.querySelectorAll('[data-testid^="filter-grid-option-"]')]
      .filter((el) => el.querySelector('[data-testid^="color_code_"]'));
  }

  function colourOptionLabel(el) {
    const code = el.querySelector('[data-testid^="color_code_"]')?.dataset.testid || "";
    const title = el.querySelector('[class*="web_ui__Cell__title"]');
    return {
      text: ((title ? title.textContent : el.textContent) || "").trim().toLowerCase(),
      code: code.replace("color_code_", "").replace(/-/g, " ").toLowerCase(),
    };
  }

  // Heeft een optie zijn eigen vinkje aangezet? Bij de lijstvorm blijft de
  // trigger-waarde soms leeg tot het paneel dichtgaat; het vinkje is dan het
  // enige bewijs dat de klik is aangekomen.
  function colourOptionChecked(el) {
    if (!el) return false;
    const box = el.querySelector('input[type="checkbox"], input[type="radio"]');
    if (box && box.checked) return true;
    if (el.getAttribute?.("aria-checked") === "true") return true;
    if (el.getAttribute?.("aria-selected") === "true") return true;
    return !!el.querySelector('[aria-checked="true"], [aria-selected="true"]');
  }

  // Eén klik, en dan STOPPEN zodra er iets gebeurt.
  //
  // Dit was de eigenlijke oorzaak dat de kleur leeg bleef. De oude versie klikte
  // net zo lang door tot het kleurveld een waarde toonde — maar bij een
  // kleurtegel vult Vinted dat veld pas als het paneel dichtgaat. De eerste klik
  // vinkte de kleur dus gewoon aan, wij zagen "nog leeg", klikten nóg een keer,
  // en zetten hem daarmee weer uít. Even vaak aan als uit = leeg.
  //
  // Daarom kijken we nu of de tegel zélf reageert: verandert er iets in die tegel
  // (vinkje, aria-status, een klasse, een vinkicoon), dan is de klik aangekomen
  // en houden we onmiddellijk op met klikken.
  async function clickColourOption(opt, isSet) {
    const targets = [
      opt.querySelector('input[type="checkbox"], input[type="radio"]'),
      opt,
      opt.querySelector('[data-testid^="color_code_"]'),
      opt.querySelector('[class*="color-select-item"]')
        || opt.querySelector('[class*="web_ui__Cell__title"]')
        || opt.firstElementChild,
    ].filter((el, i, arr) => el && arr.indexOf(el) === i);

    for (const t of targets) {
      const voor = opt.outerHTML;
      const gereageerd = () =>
        !opt.isConnected || opt.outerHTML !== voor || colourOptionChecked(opt) || isSet();
      if (t.tagName === "INPUT") t.click(); else humanClickEl(t);
      // De tegel is van uiterlijk of status veranderd → de klik is aangekomen.
      if (await waitUntil(gereageerd, 1500)) return true;
    }
    return isSet();
  }

  // Elk element dat op DIT moment een aanklikbare keuze-optie is, ongeacht welk
  // paneel erbij hoort. Alleen bruikbaar in combinatie met een momentopname van
  // vóór het openklikken — zie fillColourVinted.
  function anyOptionEls() {
    return [
      ...document.querySelectorAll('[data-testid^="filter-grid-option-"]'),
      ...document.querySelectorAll('[class*="web_ui__Cell__cell"]'),
    ];
  }

  function findColourOption(want, optionEls) {
    const w = want.toLowerCase().trim();
    const opts = (optionEls || colourOptionEls()).map((el) => ({ el, ...colourOptionLabel(el) }));
    if (!opts.length) return null;
    const base = w.replace(/^(licht|donker|light|dark)\s*/i, "").trim();
    return (
      opts.find((o) => o.text === w || o.code === w) ||
      opts.find((o) => o.text.startsWith(w) || o.code.startsWith(w)) ||
      opts.find((o) => o.text.includes(w) || o.code.includes(w)) ||
      (base && base !== w
        ? opts.find((o) => o.text === base || o.code === base) ||
          opts.find((o) => o.text.includes(base) || o.code.includes(base))
        : null) ||
      null
    )?.el || null;
  }

  async function fillColourVinted(item) {
    const colours = parseColours(item);
    if (!colours.length) {
      kleurDiagnose = "no colour on this item and nothing usable in the title";
      clog("Vinted kleur: " + kleurDiagnose);
      return false;
    }
    clog("Vinted kleur: gezocht wordt " + colours.join(" + "));

    await waitUntil(() => {
      const el = qs(COLOUR_TRIGGER_SEL);
      return el && el.offsetParent;
    }, 3000);
    const trigger = (() => {
      const el = qs(COLOUR_TRIGGER_SEL);
      return el && el.offsetParent ? el : null;
    })();
    if (!trigger) {
      kleurDiagnose = "the colour field was not on the page";
      clog("Vinted kleur: " + kleurDiagnose);
      return false;
    }

    // Waar Vinted de kleurlijst neerzet verschilt per categorie én per versie:
    // soms in een eigen container, soms als accordeon in het veld, soms — zoals
    // bij materiaal — in een zwevend paneel dat helemaal onderaan de pagina
    // hangt. Elke selector die we vooraf verzinnen is dus een gok, en juist die
    // gok liet de kleur telkens leeg.
    //
    // Daarom kijken we niet meer WAAR de opties staan, maar WELKE erbij komen:
    // we leggen vast wat er vóór de klik al aan keuzerijen op de pagina staat en
    // beschouwen alles wat daarna verschijnt als het kleurpaneel. Dat werkt bij
    // elke vorm en kan nooit een rij uit een ander (al open) paneel raken.
    let voorafBekend = null; // null = er is nog geen momentopname gemaakt
    const nieuweOpties = () =>
      voorafBekend ? anyOptionEls().filter((el) => !voorafBekend.has(el)) : [];
    const kleurOpties = () => {
      const nieuw = nieuweOpties();
      // Staan er kleurbolletjes tussen, dan zijn díé het kleurpaneel — de rest is
      // een ander paneel dat toevallig opnieuw getekend werd.
      const metBolletje = nieuw.filter((el) => el.querySelector('[data-testid^="color_code_"]'));
      if (metBolletje.length) return metBolletje;
      if (nieuw.length) return nieuw;
      // Vangnet alleen binnen de eigen container van het kleurveld. Ruimer zoeken
      // mag hier niet: dan tellen rijen van andere kenmerken mee.
      const eigen = document.querySelector('[data-testid="color-select-dropdown-content"]');
      return eigen ? colourOptionEls() : [];
    };
    const isOpen = () => kleurOpties().length > 0;

    // Het kleurVELD toont de gekozen kleur — dit is het enige oordeel dat telt
    // zolang er geen kleurpaneel open staat.
    const alGezet = () => !!(trigger.value || "").trim();
    // Tijdens het kiezen telt daarnaast een vinkje in een net verschenen
    // kleurrij. Let op: alléén in rijen die ná onze momentopname verschenen —
    // anders zag hij het al aangevinkte rondje van "Staat" (Very good) aan voor
    // een gekozen kleur en meldde de stap "gelukt" zonder ook maar iets te doen.
    const isSet = () => alGezet() || kleurOpties().some(colourOptionChecked);

    for (let attempt = 0; attempt < 2; attempt++) {
      if (alGezet()) return true;   // already set
      // The brand/size panel that ran just before us can still be open. While it
      // is, our first click merely dismisses it and never reaches the colour
      // trigger — which is exactly how colour kept ending up empty while every
      // other field was filled. Dismiss it ourselves first, every attempt.
      const outside = qs('input[data-testid="title--input"]');
      if (outside) { realClickEl(outside); await sleep(400); }
      // Momentopname NA het sluiten van andere panelen: alles wat hierna
      // verschijnt hoort bij de kleur.
      voorafBekend = new Set(anyOptionEls());
      if (!(await openDropdownVinted(trigger, isOpen))) {
        kleurDiagnose = "the colour field would not open (attempt " + (attempt + 1) + ")";
        clog("Vinted kleur: " + kleurDiagnose);
        continue;
      }
      const zichtbaar = kleurOpties().map((e) => colourOptionLabel(e).text).filter(Boolean);
      clog(`Vinted kleur: paneel open, ${zichtbaar.length} opties, bv. ${zichtbaar.slice(0, 8).join(" / ")}`);

      let geklikt = false;
      for (const colour of colours) {
        const opts = kleurOpties();
        const opt = findColourOption(colour, opts);
        if (!opt) {
          kleurDiagnose = `"${colour}" was not in Vinted's list of ${opts.length} colours `
            + `(${opts.map((e) => colourOptionLabel(e).text).filter(Boolean).slice(0, 15).join(", ")})`;
          clog("Vinted kleur: " + kleurDiagnose);
          continue;
        }
        opt.scrollIntoView({ block: "center" });
        await sleep(250);
        if (await clickColourOption(opt, isSet)) geklikt = true;
      }

      // Het kleurveld toont zijn waarde bij sommige vormen pas als het paneel
      // dicht is. Sluiten en dán pas oordelen — anders concluderen we onterecht
      // dat het misging en gaan we opnieuw klikken (wat de kleur weer uitzet).
      if (outside) {
        realClickEl(outside);
        await waitUntil(() => alGezet() || !isOpen(), 2000);
      }
      if ((trigger.value || "").trim()) {
        clog("Vinted kleur: gezet op " + trigger.value);
        return true;
      }
      if (geklikt && isSet()) {
        clog("Vinted kleur: aangevinkt (veld toont de waarde nog niet)");
        return true;
      }
      kleurDiagnose = geklikt
        ? "the colour was clicked but Vinted did not take it"
        : "none of the colour tiles responded to a click";
      clog("Vinted kleur: " + kleurDiagnose + " — nog een poging");
      await sleep(400);
    }

    // Alles op deze route mislukt: probeer nog de generieke kenmerk-invuller,
    // die de lijstvorm langs een andere weg aanklikt. Beter één extra poging dan
    // een zoekertje dat blijft hangen op "Fill in colour to continue".
    clog("Vinted kleur: laatste poging via de generieke invuller");
    await fillAttributeVinted(["colour"], colours[0]);
    await sleep(500);
    const outsideEl = qs('input[data-testid="title--input"]');
    if (outsideEl) { realClickEl(outsideEl); await sleep(700); }
    if ((trigger.value || "").trim()) {
      clog("Vinted kleur: alsnog gezet op " + trigger.value);
      return true;
    }
    return false;
  }

  async function fillMaterialFromOpenPanel(value) {
    if (!value) return false;
    const translated = MATERIAL_MAP[value.toLowerCase().trim()] || value;
    const w = translated.toLowerCase().trim();

    // Poll up to 2s for the panel list items to appear.
    let titleEls = [];
    for (let i = 0; i < 20; i++) {
      // Query ALL title elements — no offsetParent filter (items may be scrolled out of view).
      titleEls = [...document.querySelectorAll('[class*="web_ui__Cell__title"]')];
      if (titleEls.length > 0) break;
      await sleep(100);
    }
    if (!titleEls.length) { console.warn("[Omnivaleur] material panel: no items found"); return false; }

    // Exact match first, then partial.
    let best = titleEls.find(e => e.textContent.trim().toLowerCase() === w);
    if (!best) best = titleEls.find(e => e.textContent.trim().toLowerCase().includes(w));
    if (!best) best = titleEls.find(e => w.includes(e.textContent.trim().toLowerCase()) && e.textContent.trim().length > 2);
    if (!best) { console.warn("[Omnivaleur] Vinted material not found:", value, "→", translated); return false; }

    // Scroll the item into view within the dropdown container, then realClick it.
    best.scrollIntoView({ block: "nearest" });
    await sleep(200);
    const cell = best.closest('[class*="web_ui__Cell__cell"]') || best.parentElement || best;
    realClickEl(cell);
    await sleep(500);
    console.log("[Omnivaleur] material selected:", translated);
    return true;
  }

  // ---- Generic attribute filler (condition/size/brand/colour/material).
  // Trigger inputs (readonly c-input__value) open panels when clicked.
  // - Condition/colour/material: options in web_ui__Cell__title elements.
  // - Size: options in filter-grid__option elements (grid layout).
  // - Brand: trigger is a TOGGLE — only click if search panel is currently closed.
  //   Brand search input is always inside the same container; type to filter, then pick. ----
  async function fillAttributeVinted(fieldKeys, value) {
    if (!value) return false;

    const ATTR_FIELD_MAP = {
      condition: "category-condition-single-list-input",
      status:    "category-condition-single-list-input",
      size:      "category-size-single-grid-input",
      brand:     "brand-select-dropdown-input",
      colour:    "color-select-dropdown-input",
      color:     "color-select-dropdown-input",
      colours:   "color-select-dropdown-input",
      colors:    "color-select-dropdown-input",
      material:  "category-material-multi-list-input",
    };

    const keys = fieldKeys.map(k => k.toLowerCase());
    const isBrand = keys.includes("brand");
    const isSize  = keys.includes("size");

    // Wacht tot het veld getekend is — op de verandering, niet op de klok.
    const zoekTrigger = () => {
      for (const key of keys) {
        const testId = ATTR_FIELD_MAP[key];
        if (!testId) continue;
        const el = document.querySelector(`input[data-testid="${testId}"]`);
        if (el && el.offsetParent) return el;
      }
      // Size renders as a grid for some categories and as a plain dropdown/list
      // for others ("Select a size" with a chevron). Hard-coding the grid testid
      // meant the whole size step silently gave up on those categories — and a
      // failed size step used to leave a panel open that then broke colour too.
      if (isSize) {
        return [...document.querySelectorAll('input[data-testid^="category-size"][data-testid$="-input"]')]
          .find(el => el.offsetParent) || null;
      }
      return null;
    };
    await waitUntil(() => !!zoekTrigger(), 3000);
    const triggerEl = zoekTrigger();
    if (!triggerEl) {
      console.warn("[Omnivaleur] Vinted attr not found:", fieldKeys);
      return false;
    }

    if (isBrand) {
      // Brand panel is a toggle: only click trigger if search input is NOT visible.
      const zoekveld = () => {
        const el = document.querySelector('input[data-testid="brand-search--input"]');
        return el && el.offsetParent ? el : null;
      };
      if (!zoekveld()) {
        realClickEl(triggerEl);
        await waitUntil(() => !!zoekveld(), 2500);
      }
      const brandSearch = zoekveld();
      if (brandSearch) {
        fillInput(brandSearch, value);
        await waitUntil(
          () => [...document.querySelectorAll('[class*="web_ui__Cell__title"]')]
            .some((e) => e.textContent.toLowerCase().includes(value.toLowerCase())),
          2500);
      }
    } else if (!isSize) {
      // All other fields: click trigger to open panel. Scroll it into view
      // first — a click on an off-screen trigger does nothing on Vinted.
      triggerEl.scrollIntoView({ block: "center" });
      realClickEl(triggerEl);
      await waitUntil(
        () => [...document.querySelectorAll('[class*="web_ui__Cell__title"]')].some((e) => e.offsetParent),
        2500);
    }

    const lv = value.toLowerCase();

    if (isSize) {
      // Verified against the live form: size options are
      // [data-testid="size-group-<n>-grid-option-<id>"] inside
      // [data-testid="category-size-single-grid-content"]. The old
      // `filter-grid__option` class no longer exists, which is why every size
      // attempt silently failed. Scope to the size panel so we can never click
      // a package-size or colour tile by accident.
      const sizeOptEls = () => {
        const scope = document.querySelector('[data-testid="category-size-single-grid-content"]');
        return scope
          ? [...scope.querySelectorAll('[data-testid*="-grid-option-"]')]
          : [...document.querySelectorAll('[data-testid^="size-group-"][data-testid*="-grid-option-"]')];
      };
      if (!(await openDropdownVinted(triggerEl, () => sizeOptEls().length > 0))) {
        console.warn("[Omnivaleur] Vinted size panel didn't open");
        return false;
      }
      const opts = sizeOptEls();
      // Everything this size could reasonably be called on Vinted: as given,
      // without an "EU " prefix, the word form ("large" → "L"), and the waist
      // form ("44" → "W44") that trousers/shorts use.
      const SIZE_WORDS = {
        "extra small": "xs", "x-small": "xs", "xsmall": "xs",
        "small": "s", "medium": "m", "large": "l",
        "extra large": "xl", "x-large": "xl", "xlarge": "xl",
        "extra extra large": "xxl", "one size": "one size", "onesize": "one size",
      };
      const norm = lv.replace(/^eu\s*/i, "").replace(/\s+/g, " ").trim();
      const wants = new Set([lv, norm]);
      if (SIZE_WORDS[norm]) wants.add(SIZE_WORDS[norm]);
      for (const [word, abbr] of Object.entries(SIZE_WORDS)) if (abbr === norm) wants.add(word);
      if (/^\d+$/.test(norm)) { wants.add("w" + norm); wants.add(norm + " "); }
      if (/^w\d+$/.test(norm)) wants.add(norm.slice(1));

      const label = (e) => (e.textContent || "").trim().toLowerCase();
      let match = opts.find(e => wants.has(label(e)));
      if (!match) {
        // Combined labels ("M / 38 / 10") — compare each part.
        match = opts.find(e => label(e).split("/").map(x => x.trim()).some(x => wants.has(x)));
      }
      if (!match && /^\d+$/.test(norm)) {
        // Shirt collar sizes read "18 in | 44 cm" — the number IS our size, just
        // dressed up. Prefer this over the letter fallback below: it is the exact
        // size, not an approximation.
        const cm = new RegExp("(^|[^\\d])" + norm + "\\s*cm\\b");
        match = opts.find(e => cm.test(label(e)));
        if (match) console.log("[Omnivaleur] Vinted size", value, "→", label(match));
      }
      if (!match && /^\d+$/.test(norm)) {
        // Numbered sizes that this category simply doesn't offer. Men's tops on
        // Vinted only list letters (XS…8XL), so a shirt labelled 44 had no
        // option to click at all. Translate collar/suit sizes to their letter
        // equivalent — but only as a last resort, after every literal match
        // failed, so a category that DOES have numbers keeps using them.
        const NUM_TO_LETTER = {
          36: "xs", 37: "s", 38: "s", 39: "m", 40: "m", 41: "l", 42: "l",
          43: "xl", 44: "xl", 45: "xxl", 46: "xxl",
          48: "s", 50: "m", 52: "l", 54: "xl", 56: "xxl", 58: "xxxl",
        };
        const letter = NUM_TO_LETTER[parseInt(norm, 10)];
        if (letter) {
          match = opts.find(e => label(e) === letter);
          if (match) console.log("[Omnivaleur] Vinted size", value, "→", letter, "(category has letter sizes only)");
        }
      }
      if (!match) {
        console.warn("[Omnivaleur] Vinted size option not found:", value,
                     "| wanted:", [...wants], "| available:", opts.map(label).slice(0, 25));
        // Leave nothing open behind us: a size panel that stays up covers the
        // colour field, and then the colour click lands on the panel instead.
        const outside = qs('input[data-testid="title--input"]');
        if (outside) { realClickEl(outside); await sleep(400); }
        return false;
      }
      match.scrollIntoView({ block: "center" });
      await sleep(150);
      realClickEl(match);
      await sleep(600);
      const ok = !!(triggerEl.value || "").trim();
      if (!ok) console.warn("[Omnivaleur] Vinted size click didn't stick:", value);
      return ok;
    }

    // Condition / colour / material / brand: options in web_ui__Cell__title.
    // Scope to the currently-open panel via closest ancestor with a "content" or "overlay" class,
    // or fall back to all visible titles.
    const allTitles = [...document.querySelectorAll('[class*="web_ui__Cell__title"]')]
      .filter(e => e.offsetParent);

    // Fuzzy scorer: exact → startsWith → includes → word-overlap
    const fuzzyScore = (text, want) => {
      const t = text.toLowerCase().trim();
      const w = want.toLowerCase().trim();
      if (t === w) return 4;
      if (t.startsWith(w) || w.startsWith(t)) return 3;
      if (t.includes(w) || w.includes(t)) return 2;
      // Word-overlap score
      const tw = new Set(t.split(/\s+/));
      const ww = w.split(/\s+/);
      const hits = ww.filter(word => tw.has(word) || [...tw].some(tt => tt.includes(word))).length;
      return hits > 0 ? hits / ww.length : 0;
    };

    let best = null, bestScore = 0;
    for (const el of allTitles) {
      const s = fuzzyScore(el.textContent, value);
      if (s > bestScore) { best = el; bestScore = s; }
    }

    if (!best || bestScore === 0) {
      console.warn("[Omnivaleur] Vinted attr option not found:", fieldKeys, value);
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      return false;
    }

    console.log(`[Omnivaleur] Vinted attr "${fieldKeys}" matched "${best.textContent.trim()}" (score ${bestScore}) for value "${value}"`);
    const cell = best.closest('[class*="web_ui__Cell__cell"]') || best;

    // Colour uses checkboxes (multi-select), condition/material use radios (single-select).
    // Clicking the outer div does NOT trigger React's checkbox/radio handler — click the input directly.
    const inputInCell = cell.querySelector('input[type="checkbox"], input[type="radio"]');
    if (inputInCell) {
      inputInCell.click();
    } else {
      realClickEl(cell);
    }
    await sleep(400);
    // Do NOT send Escape here — Escape reverts colour checkboxes. The value is already
    // committed to React state the moment the checkbox/radio is clicked. Inline accordion
    // panels can stay open; the next step opening its own panel causes no interference
    // because each field's fuzzy search is value-specific enough to avoid cross-panel hits.
    return true;
  }

  // Ask the background for THIS tab's own job (keyed by tab id), so two tabs can
  // never read each other's data. Retry briefly: the tab can finish loading
  // before the background has stored the job.
  function getJob() {
    return new Promise((resolve) => {
      let tries = 0;
      const ask = () => {
        chrome.runtime.sendMessage({ type: "GET_JOB" }, (resp) => {
          if (chrome.runtime.lastError) { /* background not ready yet */ }
          if (resp && resp.job) return resolve(resp.job);
          if (++tries < 20) return setTimeout(ask, 150);
          resolve(null);
        });
      };
      ask();
    });
  }
  function send(type, result, errorMsg) {
    chrome.runtime.sendMessage({ type, platform: PLATFORM, jobId, serverUrl, result, error: errorMsg });
  }
})();
