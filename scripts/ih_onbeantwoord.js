// Indie Hackers: welke reacties onder een post hebben nog geen antwoord van danieldk04?
// Gebruik: plak dit in javascript_tool op een geopende /post/...-pagina (Claude in Chrome).
// Geeft {alle, onbeantwoord}; elke onbeantwoorde heeft een sleutel voor `bip_reacties.py is-gezien/gezien`.
// Een reactie telt als beantwoord zodra een DIRECTE reactie eronder van danieldk04 is.
// Opbouw van de pagina (17-11-2026): ul.comment-tree > li > (div.comment + ul.comment-tree > li ...).
(() => {
  const IK = 'danieldk04';
  const slug = (location.pathname.split('/post/')[1] || '').slice(0, 60);
  const auteurVan = (c) => ((c.querySelector('.comment__footer') || {}).innerText || '').split('\n')[0].trim();
  const uit = []; const alle = [];
  const loop = (li, diepte) => {
    const comment = li.querySelector(':scope > .comment');
    if (!comment) return;
    const kids = [...li.querySelectorAll(':scope > .comment-tree > li')];
    const auteur = auteurVan(comment);
    const tekst = ((comment.querySelector('.comment__content') || comment).innerText || '').trim().replace(/\s+/g, ' ');
    const beantwoord = kids.some(k => { const c = k.querySelector(':scope > .comment'); return c && auteurVan(c) === IK; });
    alle.push(auteur + (beantwoord ? ' [beantwoord]' : '') + ' d' + diepte);
    if (auteur && auteur !== IK && !beantwoord) uit.push({ sleutel: `ih:${slug}:${auteur}:${tekst.slice(0, 30)}`, auteur, tekst: tekst.slice(0, 300), diepte });
    kids.forEach(k => loop(k, diepte + 1));
  };
  document.querySelectorAll('.embedded-comments > .comment-tree > li').forEach(li => loop(li, 1));
  return { alle, onbeantwoord: uit };
})()
