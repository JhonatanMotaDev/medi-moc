(() => {
  // Busca de medicamentos, filtros do catálogo e mapa das unidades.
  // Busca de medicamentos, filtros do catálogo e mapa das unidades.
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  // Helpers compartilhados de texto, animação e atraso da pesquisa.
  const normalize = (value) =>
    (value || "").normalize("NFKD").replace(/\p{Diacritic}/gu, "").toLowerCase();

  const scrollToElement = (element, block = "start") => {
    element?.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block });
  };

  const debounce = (callback, delay) => {
    let timer;
    return (...args) => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => callback(...args), delay);
    };
  };

  // Configura sugestões acessíveis e navegação por teclado para a busca.
  // Configura sugestões acessíveis e navegação por teclado para a busca.
  function initAutocomplete() {
    const input = document.querySelector("#medicine-search");
    const listbox = document.querySelector("#medicine-suggestions");
    const clearButton = document.querySelector("#medicine-clear");
    const status = document.querySelector("#search-status");
    if (!input || !listbox) return;

    const field = input.closest(".medicine-field");
    let items = [];
    let activeIndex = -1;
    let controller;
    let timer;
    let requestVersion = 0;

    if (clearButton) clearButton.hidden = !input.value;

    const setStatus = (message) => {
      if (status) status.textContent = message;
    };

    // Mantém a lista de sugestões e o estado do leitor de tela sincronizados.
    const closeList = () => {
      requestVersion += 1;
      window.clearTimeout(timer);
      listbox.hidden = true;
      listbox.replaceChildren();
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
      items = [];
      activeIndex = -1;
    };

    const openList = () => {
      listbox.hidden = false;
      input.setAttribute("aria-expanded", "true");
    };

    const normalizedWithMap = (value) => {
      const characters = [];
      const originalIndexes = [];
      for (let index = 0; index < value.length; index += 1) {
        const normalized = value[index]
          .normalize("NFKD")
          .replace(/\p{Diacritic}/gu, "")
          .toLowerCase();
        for (const character of normalized) {
          characters.push(character);
          originalIndexes.push(index);
        }
      }
      return { text: characters.join(""), indexes: originalIndexes };
    };

    const highlightedText = (name, query) => {
      const fragment = document.createDocumentFragment();
      const normalizedName = normalizedWithMap(name);
      const normalizedQuery = normalize(query);
      const position = normalizedName.text.indexOf(normalizedQuery);
      if (!normalizedQuery || position === -1) {
        fragment.append(document.createTextNode(name));
        return fragment;
      }

      const start = normalizedName.indexes[position];
      const end = normalizedName.indexes[position + normalizedQuery.length - 1] + 1;
      if (start > 0) fragment.append(document.createTextNode(name.slice(0, start)));
      const mark = document.createElement("mark");
      mark.textContent = name.slice(start, end);
      fragment.append(mark);
      if (end < name.length) fragment.append(document.createTextNode(name.slice(end)));
      return fragment;
    };

    const setActive = (index) => {
      const options = Array.from(listbox.querySelectorAll('[role="option"]'));
      if (!options.length) return;
      activeIndex = Math.max(0, Math.min(index, options.length - 1));
      options.forEach((option, optionIndex) => {
        const isActive = optionIndex === activeIndex;
        option.classList.toggle("is-active", isActive);
        option.setAttribute("aria-selected", isActive ? "true" : "false");
      });
      const active = options[activeIndex];
      input.setAttribute("aria-activedescendant", active.id);
      active.scrollIntoView({ block: "nearest" });
    };

    const selectItem = (name) => {
      input.value = name;
      clearButton?.removeAttribute("hidden");
      closeList();
      setStatus(`Medicamento selecionado: ${name}.`);
      input.form?.requestSubmit();
    };

    const renderItems = (names, query) => {
      listbox.replaceChildren();
      items = names;
      activeIndex = -1;
      if (!names.length) {
        const empty = document.createElement("p");
        empty.className = "suggestion-empty";
        empty.textContent = "Nenhum medicamento encontrado. Confira a escrita ou tente uma parte menor do nome.";
        listbox.append(empty);
        openList();
        setStatus("Nenhuma sugestão encontrada.");
        return;
      }

      names.forEach((name, index) => {
        const option = document.createElement("div");
        option.id = `medicine-option-${index}`;
        option.className = "suggestion-item";
        option.setAttribute("role", "option");
        option.setAttribute("aria-selected", "false");
        option.dataset.value = name;
        option.append(highlightedText(name, query));
        listbox.append(option);
      });
      openList();
      setStatus(`${names.length} sugestões disponíveis. Use as setas para navegar.`);
    };

    // Descarta respostas antigas para não sobrescrever a busca atual.
    const fetchSuggestions = async (query, version) => {
      controller?.abort();
      controller = new AbortController();
      try {
        const response = await fetch(`/api/medicines?q=${encodeURIComponent(query)}`, {
          signal: controller.signal,
          headers: { Accept: "application/json" },
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const names = await response.json();
        if (version !== requestVersion) return;
        renderItems(Array.isArray(names) ? names : [], query);
      } catch (error) {
        if (error.name !== "AbortError" && version === requestVersion) {
          closeList();
          setStatus("Não foi possível carregar sugestões. Você ainda pode buscar pelo nome.");
          console.error("Não foi possível carregar sugestões de medicamentos.", error);
        }
      }
    };

    input.addEventListener("input", () => {
      window.clearTimeout(timer);
      controller?.abort();
      requestVersion += 1;
      const version = requestVersion;
      const query = input.value.trim();
      clearButton?.toggleAttribute("hidden", !input.value);
      if (query.length < 2) {
        closeList();
        setStatus("");
        return;
      }
      timer = window.setTimeout(() => fetchSuggestions(query, version), 180);
    });

    input.addEventListener("keydown", (event) => {
      if (listbox.hidden) return;
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setActive(activeIndex + 1);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        setActive(activeIndex - 1);
      } else if (event.key === "Enter" && activeIndex >= 0) {
        event.preventDefault();
        selectItem(items[activeIndex]);
      } else if (event.key === "Escape") {
        closeList();
      } else if (event.key === "Tab") {
        closeList();
      }
    });

    input.addEventListener("blur", () => {
      window.setTimeout(() => {
        if (!field?.contains(document.activeElement)) closeList();
      }, 120);
    });

    listbox.addEventListener("mousedown", (event) => event.preventDefault());
    listbox.addEventListener("click", (event) => {
      const option = event.target.closest('[role="option"]');
      if (option?.dataset.value) selectItem(option.dataset.value);
    });

    clearButton?.addEventListener("click", () => {
      controller?.abort();
      input.value = "";
      clearButton.setAttribute("hidden", "");
      closeList();
      input.focus();
      setStatus("Busca limpa.");
    });

    input.form?.addEventListener("submit", closeList);
  }

  // Aplica imediatamente os filtros de unidade e ordenação.
  // Aplica imediatamente os filtros de unidade e ordenação.
  function initAutoSubmit() {
    document.querySelectorAll("[data-autosubmit]").forEach((select) => {
      select.addEventListener("change", () => select.form?.requestSubmit());
    });
  }

  // Mantém pesquisa, seleção, diretório e mapa apontando para a mesma unidade.
  // Mantém pesquisa, seleção, diretório e mapa apontando para a mesma unidade.
  function initMap() {
    const mapFrame = document.querySelector("#unit-map");
    const mapSearch = document.querySelector("#map-unit-search");
    const mapUnitSelect = document.querySelector("#map-unit-select");
    const mapMyLocation = document.querySelector("#map-my-location");
    const mapNote = document.querySelector("#map-location-note");
    const mapExternalLink = document.querySelector("#map-external-link");
    const mappedFilter = document.querySelector("#map-filter-mapped");
    const directoryCount = document.querySelector("#directory-count");
    const directoryEmpty = document.querySelector("#directory-empty");
    const directory = document.querySelector(".unit-directory");
    const locateButtons = Array.from(document.querySelectorAll("[data-map-unit]"));
    const directoryRows = Array.from(document.querySelectorAll("[data-directory-unit]"));
    if (!mapFrame || !mapNote) return;

    const unitsById = new Map();
    for (const button of locateButtons) {
      const unitId = button.dataset.mapUnit;
      if (!unitId || unitsById.has(unitId)) continue;
      unitsById.set(unitId, {
        unitId,
        name: button.dataset.mapName || "",
        address: button.dataset.mapAddress || "",
        status: button.dataset.mapStatus || "",
      });
    }

    const cityCenter = [-16.725, -43.86];
    const mapsSearchUrl = (name, rawAddress) => {
      const address = (rawAddress || "").replace(/\s*[-–]\s*Telefones?:.*$/i, "");
      const query = [name, address, "Montes Claros", "MG"].filter(Boolean).join(", ");
      return `https://www.google.com/maps/search/?api=1&${new URLSearchParams({ query })}`;
    };

    const setExternalLink = (unit) => {
      if (!mapExternalLink) return;
      if (!unit) {
        mapExternalLink.hidden = true;
        return;
      }
      mapExternalLink.href = mapsSearchUrl(unit.name, unit.address);
      mapExternalLink.hidden = false;
    };

    const updateButtonLabels = (mapped) => {
      for (const button of locateButtons) {
        const label = button.querySelector("span");
        const isMapped = mapped.has(button.dataset.mapUnit);
        if (label) label.textContent = isMapped ? "Ver no mapa" : "Pesquisar no Google Maps";
        button.dataset.mapStatus = isMapped ? "mapped" : "unmapped";
      }
    };

    // Aplica o mesmo texto e filtro de pinos a cada linha do diretório.
    const filterDirectory = () => {
      const query = normalize(mapSearch?.value);
      const onlyMapped = Boolean(mappedFilter?.checked);
      let visible = 0;
      for (const row of directoryRows) {
        const matchesText = !query || normalize(row.dataset.directorySearch).includes(query);
        const matchesMap = !onlyMapped || row.dataset.directoryMapped === "true";
        const matches = matchesText && matchesMap;
        row.hidden = !matches;
        if (matches) visible += 1;
      }

      if (directoryCount) {
        directoryCount.textContent = query || onlyMapped
          ? `${visible} de ${directoryRows.length} unidades correspondem ao filtro.`
          : `${directoryRows.length} unidades listadas. Use a pesquisa acima para filtrar.`;
      }
      if (directoryEmpty) directoryEmpty.hidden = visible !== 0;
      if ((query || onlyMapped) && directory) directory.open = true;
      return { visible, query, onlyMapped };
    };

    const wireFallback = () => {
      for (const button of locateButtons) {
        const label = button.querySelector("span");
        if (label) label.textContent = "Pesquisar no Google Maps";
        button.addEventListener("click", () => {
          setExternalLink(unitsById.get(button.dataset.mapUnit));
          mapExternalLink?.focus();
        });
      }
      mapUnitSelect?.addEventListener("change", () => {
        setExternalLink(unitsById.get(mapUnitSelect.value));
      });
      wireDirectoryFilters();
    };

    const wireDirectoryFilters = () => {
      mapSearch?.addEventListener("input", filterDirectory);
      mappedFilter?.addEventListener("change", filterDirectory);
      filterDirectory();
    };

    if (!window.L) {
      mapFrame.classList.add("is-unavailable");
      mapFrame.textContent = "O mapa interativo não carregou. Use a pesquisa e o diretório abaixo para encontrar a unidade.";
      mapNote.textContent = "O mapa interativo não carregou. Use a pesquisa no diretório e o link para o Google Maps.";
      if (mapMyLocation) {
        mapMyLocation.disabled = true;
        mapMyLocation.title = "Indisponível porque o mapa interativo não carregou.";
      }
      console.error("Leaflet não foi carregado; o mapa interativo está indisponível.");
      wireFallback();
      return;
    }

    const map = window.L.map(mapFrame).setView(cityCenter, 12);
    let userMarker;
    window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
    }).addTo(map);

    const makePopup = (location) => {
      const content = document.createElement("div");
      const name = document.createElement("strong");
      name.textContent = location.name;
      content.append(name);

      const status = document.createElement("div");
      status.textContent = location.location_status === "provisional"
        ? "Localização provisória por endereço"
        : "Ponto publicado/verificado";
      content.append(status);

      if (location.osm_address) {
        const address = document.createElement("div");
        address.textContent = location.osm_address;
        content.append(address);
      }
      if (location.source_address_note) {
        const note = document.createElement("div");
        note.textContent = location.source_address_note;
        content.append(note);
      }

      const link = document.createElement("a");
      link.href = location.osm_url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = "Ver no OpenStreetMap";
      content.append(link);
      return content;
    };

    const mappedLocations = new Map();

    const showUnit = (unitId, { scroll = false } = {}) => {
      const unit = unitsById.get(unitId);
      if (!unit) return;
      const location = mappedLocations.get(unitId);
      map.closePopup();

      if (location) {
        map.setView([location.latitude, location.longitude], 16);
        location.marker.openPopup();
        mapNote.textContent = `${unit.name} · localização no OpenStreetMap. Endereço da fonte: ${unit.address || location.source_address}.`;
        if (mapExternalLink) mapExternalLink.hidden = true;
      } else {
        map.setView(cityCenter, 12);
        mapNote.textContent = `${unit.name} não tem pino confirmado neste mapa. Consulte o endereço da fonte e pesquise antes de sair.`;
        setExternalLink(unit);
      }

      if (scroll) scrollToElement(document.querySelector("#unit-map-title"));
    };

    const handleLocations = (data) => {
      const markers = [];
      for (const location of data.locations || []) {
        const unit = unitsById.get(String(location.unit_id));
        if (!unit) continue;
        const marker = window.L.marker([location.latitude, location.longitude], {
          title: location.name,
          alt: location.name,
          icon: window.L.divIcon({
            className: `unit-map-marker ${location.location_status || "verified"}`,
            html: '<span aria-hidden="true"></span>',
            iconSize: [16, 16],
            iconAnchor: [8, 8],
          }),
        })
          .addTo(map)
          .bindPopup(makePopup(location));
        mappedLocations.set(unit.unitId, { ...location, marker });
        markers.push(marker);
      }

      mapNote.textContent = `${mappedLocations.size} de ${unitsById.size} unidades aparecem mapeadas no OpenStreetMap. Selecione uma unidade para ver o ponto ou use a pesquisa.`;
      if (markers.length > 1) {
        map.fitBounds(window.L.featureGroup(markers).getBounds().pad(0.15), { maxZoom: 13 });
      }

      updateButtonLabels(mappedLocations);
      for (const row of directoryRows) {
        row.dataset.directoryMapped = mappedLocations.has(row.dataset.directoryUnit) ? "true" : "false";
      }
      filterDirectory();
    };

    mapSearch?.addEventListener("input", debounce(() => {
      const { visible, query } = filterDirectory();
      if (query && visible === 1) {
        const row = directoryRows.find((candidate) => !candidate.hidden);
        if (row) showUnit(row.dataset.directoryUnit);
      }
    }, 120));
    mappedFilter?.addEventListener("change", filterDirectory);

    for (const button of locateButtons) {
      button.addEventListener("click", () => {
        showUnit(button.dataset.mapUnit, { scroll: true });
      });
    }

    mapUnitSelect?.addEventListener("change", () => {
      if (mapUnitSelect.value) showUnit(mapUnitSelect.value, { scroll: true });
    });

    directory?.addEventListener("toggle", () => {
      if (directory.open) window.setTimeout(() => map.invalidateSize(), 60);
    });

    mapMyLocation?.addEventListener("click", () => {
      if (!navigator.geolocation) {
        mapNote.textContent = "Seu navegador não oferece localização. Escolha uma unidade ou pesquise no diretório.";
        return;
      }
      mapNote.textContent = "Solicitando sua localização...";
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const current = [position.coords.latitude, position.coords.longitude];
          map.setView(current, 13);
          userMarker?.remove();
          userMarker = window.L.circleMarker(current, {
            radius: 7,
            color: "#15598a",
            fillColor: "#15598a",
            fillOpacity: 0.9,
          }).addTo(map).bindPopup("Sua localização aproximada neste navegador.").openPopup();
          mapNote.textContent = "Mapa centralizado na sua localização. Ela não é enviada para este projeto.";
        },
        () => {
          mapNote.textContent = "Não foi possível obter sua localização. Escolha uma unidade ou pesquise no diretório.";
        },
        { enableHighAccuracy: false, timeout: 8000, maximumAge: 300000 },
      );
    });

    fetch(mapFrame.dataset.locationsUrl, { headers: { Accept: "application/json" } })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then(handleLocations)
      .catch((error) => {
        mapNote.textContent = "Não foi possível carregar as localizações verificadas. Consulte os endereços no diretório.";
        console.error("Falha ao carregar os dados geográficos das unidades.", error);
        updateButtonLabels(mappedLocations);
        wireDirectoryFilters();
      });
  }

  initAutocomplete();
  initAutoSubmit();
  initMap();
})();
