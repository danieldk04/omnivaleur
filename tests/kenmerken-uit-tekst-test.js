// Proef voor frontend/kenmerken-uit-tekst.js. Eén regel: liever leeg dan fout.
const K = require("../frontend/kenmerken-uit-tekst.js");
const MATEN = ["One size","XXS","XS","S","M","L","XL","XXL","3XL","4XL","36","38","40","42","44","W30","W32","W34"];
const KLEUREN = ["Black","Grey","White","Cream","Beige","Orange","Red","Burgundy","Pink","Purple","Lilac","Light blue","Blue","Navy","Turquoise","Green","Dark green","Khaki","Brown","Mustard","Yellow","Silver","Gold"];
const CATS = ["heren jassen","heren hoodies","heren truien","heren jeans","heren chinos","heren shorts","heren polo's","heren t-shirts","heren overhemden","jassen","hoodies","truien","jeans","broeken","shorts","tops","blouses","jurken casual","rokken"];
let fout = 0;
const eq = (naam, got, want) => { const ok = got === want; if (!ok) fout++; console.log(`${ok ? "ok  " : "STUK"} ${naam} → ${got} ${ok ? "" : "(verwacht " + want + ")"}`); };

const T721 = "(721) Beige Ralph Lauren Fleece Jacket - Men M - Very Good";
eq("groep 721", K.doelgroep(T721), "heren");
eq("cat 721", K.categorie(T721, "heren", CATS), "heren jassen");
eq("kleur 721", K.kleur(T721, KLEUREN), "Beige");
eq("maat 721", K.maat(T721, "", MATEN), "M");

// categorie
eq("trui", K.categorie("Suitsupply grijze trui heren", "heren", CATS), "heren truien");
eq("hoodie", K.categorie("Nike hoodie zwart Men L", "heren", CATS), "heren hoodies");
eq("denim jacket is geen jeans", K.categorie("Levi's denim jacket Men M", "heren", CATS), "heren jassen");
eq("spijkerjas", K.categorie("Levi's spijkerjas", "heren", CATS), "heren jassen");
eq("jeans", K.categorie("Levi's 501 jeans W32 Men", "heren", CATS), "heren jeans");
eq("t-shirt is geen overhemd", K.categorie("Stone Island t-shirt Men L", "heren", CATS), "heren t-shirts");
eq("sweatshirt is hoodies", K.categorie("Champion sweatshirt Men L", "heren", CATS), "heren hoodies");
eq("overshirt: niet gokken", K.categorie("Carhartt overshirt Men L", "heren", CATS), null);
eq("jas + trui: twijfel", K.categorie("Jas trui combinatie", "heren", CATS), null);
eq("hoodie jacket: twijfel", K.categorie("Zip hoodie jacket Men M", "heren", CATS), null);
eq("Jack & Jones is geen jas", K.categorie("Jack & Jones trui Men M", "heren", CATS), "heren truien");
eq("Jack Wolfskin fleece jacket", K.categorie("Jack Wolfskin fleece jacket Men", "heren", CATS), "heren jassen");
eq("sport: niet gokken", K.categorie("Ajax voetbal shirt Men M", "heren", CATS), null);
eq("dames jurk", K.categorie("Zara jurk dames S", "dames", CATS), "jurken casual");
eq("dames top", K.categorie("H&M top dames", "dames", CATS), "tops");
eq("top condition", K.categorie("Zara jurk top condition dames", "dames", CATS), "jurken casual");
eq("geen groep: niets", K.categorie("Zara jurk", "", CATS), null);
eq("kinderkleding", K.doelgroep("Zara jas kids"), null);
eq("men en women", K.doelgroep("Unisex men women hoodie"), null);
eq("women is geen men", K.doelgroep("Zara jurk women M"), "dames");

// kleur
eq("twee kleuren", K.kleur("Zwart wit gestreepte trui", KLEUREN), null);
eq("navy blue is één kleur", K.kleur("Navy blue Polo Ralph Lauren trui", KLEUREN), "Navy");
eq("zwarte", K.kleur("Zwarte leren jas", KLEUREN), "Black");
eq("Red Wing is merk", K.kleur("Red Wing laarzen", KLEUREN), null);
eq("rose gold geen goud", K.kleur("Rose gold horloge", KLEUREN), null);
eq("mint condition", K.kleur("Zwarte jas mint condition", KLEUREN), "Black");
eq("geen kleur", K.kleur("Ralph Lauren jas Men M", KLEUREN), null);
eq("kleur niet in lijst", K.kleur("Camel jas", KLEUREN), null);

// maat
eq("size M", K.maat("Jas size M", "", MATEN), "M");
eq("maat xl", K.maat("Jas maat XL", "", MATEN), "XL");
eq("Dames S", K.maat("Zara jurk Dames S", "", MATEN), "S");
eq("W32 L34", K.maat("Levi's 501 W32 L34", "", MATEN), "W32");
eq("maat 42", K.maat("Overhemd maat 42", "", MATEN), "42");
eq("losse m in zin: niets", K.maat("Mooie jas m", "", MATEN), null);
eq("twee maten", K.maat("Jas size M of L", "", MATEN), null);
eq("omschrijving", K.maat("Mooie jas", "Size: L, valt ruim.", MATEN), "L");
eq("titel en omschrijving spreken tegen", K.maat("Jas size M", "Size L", MATEN), null);
eq("maat niet in lijst", K.maat("Jas size 5XL", "", MATEN), null);
eq("XXXL → 3XL", K.maat("Jas Men XXXL", "", MATEN), "3XL");
process.exit(fout ? 1 : 0);
