// Replica of the Vinted "list an item" widgets, modelled on the live form as seen
// in the user's screenshots. Deliberately reproduces the awkward traits that
// broke the extension before:
//   * a panel's options do NOT exist in the DOM until the panel is opened;
//   * the colour tiles TOGGLE — a second click deselects;
//   * the colour trigger only shows its value once the panel is closed;
//   * the condition radio is already checked (the false-positive trap);
//   * React-style delegated click handling at the document root.
(() => {
  const T = (sel) => document.querySelector(sel);

  const COLOURS = [
    ["Black", "#000"], ["Grey", "#888"], ["White", "#fff"], ["Cream", "#f5f2d0"],
    ["Beige", "#e8d9c0"], ["Apricot", "#f2be7e"], ["Orange", "#f08c1b"],
    ["Red", "#c0392b"], ["Burgundy", "#7b1e2b"], ["Pink", "#f3a6c0"],
    ["Purple", "#7d3c98"], ["Blue", "#2e5fa3"], ["Navy", "#1b2a4a"],
    ["Green", "#2e7d32"], ["Khaki", "#7c7b4f"], ["Brown", "#6b4a2f"],
    ["Mustard", "#d4a017"], ["Silver", "#c0c0c0"], ["Gold", "#d4af37"], ["Multi", "#ccc"],
  ];
  const MATERIALS = ["Acrylic", "Alpaca", "Bamboo", "Canvas", "Cardboard", "Cashmere",
                     "Ceramic", "Chiffon", "Cotton", "Denim", "Merino", "Wool", "Polyester"];
  const CONDITIONS = ["New with tags", "New without tags", "Very good", "Good", "Satisfactory"];
  const SIZES = ["XXS", "XS", "S", "M", "L", "XL", "XXL"];
  const BRANDS = ["Profuomo", "Nike", "Zara", "Adidas", "Levi's"];

  const state = { colours: [], material: [], condition: null, size: null, brand: null, category: null };
  window.__mock = state;

  // Failure modes, switched via ?mode=… so the awkward cases can be tested too.
  //   stuck      — the colour panel never opens (a field that ignores clicks)
  //   nocommit   — clicking a colour never registers at all
  //   wipe       — Vinted re-renders once and empties the colour again
  //   list       — the colour picker renders as a checkbox LIST, not a grid
  const MODE = new URLSearchParams(location.search).get("mode") || "";
  window.__mode = MODE;

  const panelOf = {
    colour: "#colour-panel", material: "#material-panel", condition: "#condition-panel",
    size: "#size-panel", brand: "#brand-panel", catalog: "#catalog-panel",
  };
  const triggerOf = {
    colour: '[data-testid="color-select-dropdown-input"]',
    material: '[data-testid="category-material-multi-list-input"]',
    condition: '[data-testid="category-condition-single-list-input"]',
    size: '[data-testid="category-size-single-grid-input"]',
    brand: '[data-testid="brand-select-dropdown-input"]',
    catalog: '[data-testid="catalog-select-dropdown-input"]',
  };
  let openPanel = null;

  function cell(label, kind, checked) {
    const d = document.createElement("div");
    d.className = "web_ui__Cell__cell";
    d.innerHTML = `<div class="web_ui__Cell__title">${label}</div>`;
    const box = document.createElement("input");
    box.type = kind;
    box.checked = !!checked;
    d.appendChild(box);
    return d;
  }

  function renderColour() {
    const p = T(panelOf.colour);
    p.innerHTML = "";
    // Variant: the same picker drawn as a checkbox list instead of a swatch grid.
    if (MODE === "list") {
      COLOURS.forEach(([name]) =>
        p.appendChild(cell(name, "checkbox", state.colours.includes(name))));
      return;
    }
    const head = document.createElement("div");
    head.textContent = "Suggested";
    p.appendChild(head);
    const grid = document.createElement("div");
    grid.className = "grid";
    COLOURS.forEach(([name, hex], i) => {
      const t = document.createElement("div");
      t.className = "tile";
      t.dataset.testid = `filter-grid-option-${i}`;
      t.setAttribute("aria-checked", state.colours.includes(name) ? "true" : "false");
      t.innerHTML = `<div class="bubble" data-testid="color_code_${name.toLowerCase().replace(/\s+/g, "-")}"`
        + ` style="background:${hex}"></div>${name}`;
      grid.appendChild(t);
    });
    p.appendChild(grid);
  }

  function renderList(key, items, kind, selected) {
    const p = T(panelOf[key]);
    const host = key === "brand" ? T("#brand-list") : p;
    host.innerHTML = "";
    items.forEach((label) => host.appendChild(cell(label, kind, selected.includes(label))));
  }

  function renderSize() {
    const p = T(panelOf.size);
    p.innerHTML = "";
    const grid = document.createElement("div");
    grid.className = "grid";
    SIZES.forEach((s, i) => {
      const t = document.createElement("div");
      t.className = "tile";
      t.dataset.testid = `size-group-1-grid-option-${i}`;
      t.textContent = s;
      grid.appendChild(t);
    });
    p.appendChild(grid);
  }

  function renderCatalog(query) {
    const p = T(panelOf.catalog);
    p.innerHTML = "";
    const leaves = ["Men > Jumpers & sweaters", "Men > Cardigans", "Men > T-shirts", "Women > Dresses"];
    leaves.filter((l) => !query || l.toLowerCase().includes(query.toLowerCase()))
      .forEach((l) => {
        const c = cell(l, "radio", false);
        c.querySelector(".web_ui__Cell__title").className = "web_ui__Cell__body";
        p.appendChild(c);
      });
    p.hidden = false;
  }

  // Panels only contain options while open — exactly like the real form.
  function open(key) {
    if (key === "colour" && MODE === "stuck") return; // field ignores every click
    if (openPanel && openPanel !== key) close(openPanel);
    openPanel = key;
    const p = T(panelOf[key]);
    if (key === "colour") renderColour();
    if (key === "material") renderList("material", MATERIALS, "checkbox", state.material);
    if (key === "condition") renderList("condition", CONDITIONS, "radio", state.condition ? [state.condition] : []);
    if (key === "size") renderSize();
    if (key === "brand") renderList("brand", BRANDS, "radio", state.brand ? [state.brand] : []);
    p.hidden = false;
  }

  function close(key) {
    const p = T(panelOf[key]);
    if (!p) return;
    p.hidden = true;
    if (key !== "brand") p.innerHTML = "";
    else T("#brand-list").innerHTML = "";
    // The colour field only reveals its value once the panel is closed — this is
    // the trait that made "did the click land?" impossible to judge from the field.
    if (key === "colour") {
      T(triggerOf.colour).value = state.colours.join(", ");
      // Vinted redraws the form after a later change and drops what was chosen.
      if (MODE === "wipe" && !window.__wiped && state.colours.length) {
        window.__wiped = true;
        setTimeout(() => {
          state.colours.length = 0;
          T(triggerOf.colour).value = "";
        }, 1500);
      }
    }
    if (openPanel === key) openPanel = null;
  }

  const keyForTrigger = (el) =>
    Object.keys(triggerOf).find((k) => el.matches?.(triggerOf[k]));

  // React attaches its handlers at the root and reacts to bubbled clicks.
  document.addEventListener("click", (ev) => {
    const el = ev.target;
    const trigger = el.closest?.("input") && keyForTrigger(el.closest("input"));
    if (trigger) {
      if (openPanel === trigger) close(trigger); else open(trigger);
      return;
    }

    const tile = el.closest?.(".tile");
    if (tile && openPanel === "colour") {
      if (MODE === "nocommit") return;  // click lands, Vinted ignores it
      const name = tile.textContent.trim();
      const i = state.colours.indexOf(name);
      if (i >= 0) state.colours.splice(i, 1);                 // toggles OFF again
      else if (state.colours.length < 2) state.colours.push(name);
      renderColour();
      return;
    }
    if (tile && openPanel === "size") {
      state.size = tile.textContent.trim();
      T(triggerOf.size).value = state.size;
      close("size");
      return;
    }

    const row = el.closest?.(".web_ui__Cell__cell");
    if (row && openPanel) {
      const label = row.querySelector('[class*="web_ui__Cell__"]').textContent.trim();
      if (openPanel === "colour") {
        if (MODE === "nocommit") return;
        const i = state.colours.indexOf(label);
        if (i >= 0) state.colours.splice(i, 1);
        else if (state.colours.length < 2) state.colours.push(label);
        renderColour();
      } else if (openPanel === "material") {
        const i = state.material.indexOf(label);
        if (i >= 0) state.material.splice(i, 1); else state.material.push(label);
        T(triggerOf.material).value = state.material.join(", ");
        renderList("material", MATERIALS, "checkbox", state.material);
      } else if (openPanel === "condition") {
        state.condition = label;
        T(triggerOf.condition).value = label;
        close("condition");
      } else if (openPanel === "brand") {
        state.brand = label;
        T(triggerOf.brand).value = label;
        close("brand");
      } else if (openPanel === "catalog") {
        state.category = label;
        T(triggerOf.catalog).value = label;
        close("catalog");
      }
      return;
    }

    // Click anywhere else (e.g. the title input) closes the open panel.
    if (openPanel && !el.closest?.(".panel")) close(openPanel);
  }, true);

  T(triggerOf.catalog).addEventListener("input", (e) => {
    openPanel = "catalog";
    renderCatalog(e.target.value);
  });
  T('[data-testid="brand-search--input"]').addEventListener("input", (e) => {
    const q = e.target.value.toLowerCase();
    renderList("brand", BRANDS.filter((b) => b.toLowerCase().includes(q)), "radio", []);
  });

  // Photos: show a thumbnail per accepted file, like the real uploader.
  T("#photos").addEventListener("change", (e) => {
    // Asynchronous, like a real upload to the CDN.
    [...e.target.files].forEach((_, i) => setTimeout(() => {
      const img = document.createElement("img");
      img.width = 40; img.height = 40; img.src =
        "data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==";
      T("#thumbs").appendChild(img);
    }, 600 + i * 400));
  });

  // Upload: only accepted when the form is complete, exactly like Vinted's own
  // validation — this is what proves the extension really filled everything.
  T('[data-testid="upload-form-save-button"]').addEventListener("click", () => {
    const missing = [];
    if (!T('[data-testid="title--input"]').value.trim()) missing.push("title");
    if (!T('[data-testid="description--input"]').value.trim()) missing.push("description");
    if (!T('[data-testid="price-input--input"]').value.trim()) missing.push("price");
    if (!state.condition) missing.push("condition");
    if (!state.size) missing.push("size");
    if (!state.colours.length) missing.push("colour");
    if (!T("#thumbs").children.length) missing.push("photos");
    window.__submit = { clickedAt: Date.now(), missing };
    if (missing.length) {
      document.title = "REJECTED: " + missing.join(", ");
      return;
    }
    location.hash = "#/items/1234567890-khaki-profuomo-zip-vest";
  });
})();
