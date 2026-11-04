(() => {
  const medicineInput = document.querySelector("#medicine-search");
  const suggestions = document.querySelector("#medicine-suggestions");
  if (!medicineInput || !suggestions) return;

  let debounceTimer;
  let activeController;

  medicineInput.addEventListener("input", () => {
    window.clearTimeout(debounceTimer);
    if (activeController) activeController.abort();

    const query = medicineInput.value.trim();
    suggestions.replaceChildren();
    if (query.length < 2) return;

    debounceTimer = window.setTimeout(async () => {
      activeController = new AbortController();
      try {
        const response = await fetch(`/api/medicines?q=${encodeURIComponent(query)}`, {
          signal: activeController.signal,
          headers: { Accept: "application/json" },
        });
        if (!response.ok) return;
        const names = await response.json();
        for (const name of names) {
          const option = document.createElement("option");
          option.value = name;
          suggestions.append(option);
        }
      } catch (error) {
        if (error.name !== "AbortError") {
          console.error("Não foi possível carregar sugestões de medicamentos.", error);
        }
      }
    }, 180);
  });

  document.querySelectorAll(".featured-card[data-query]").forEach((card) => {
    card.addEventListener("click", () => {
      medicineInput.value = card.dataset.query || "";
      medicineInput.form?.requestSubmit();
    });
  });

  const mapFrame = document.querySelector("#unit-map");
  const mapSearch = document.querySelector("#map-unit-search");
  const mapMyLocation = document.querySelector("#map-my-location");
  const mapNote = document.querySelector("#map-location-note");
  const mapExternalLink = document.querySelector("#map-external-link");
  const mapButtons = document.querySelectorAll(".map-unit-button[data-map-unit]");
  const directoryRows = document.querySelectorAll("[data-directory-unit]");
  if (mapFrame && mapNote) {
    const mapUnits = new Map(
      Array.from(mapButtons, (button) => [button.dataset.mapUnit, button]),
    );
    const cityCenter = [-16.725, -43.86];
    const normalize = (value) => (value || "").normalize("NFKD").replace(/\p{Diacritic}/gu, "").toLowerCase();
    const mapsSearchUrl = (name, rawAddress) => {
      const address = (rawAddress || "").replace(/\s*[-–]\s*Telefones?:.*$/i, "");
      const query = [name, address, "Montes Claros", "MG"].filter(Boolean).join(", ");
      return `https://www.google.com/maps/search/?api=1&${new URLSearchParams({ query })}`;
    };

    if (!window.L) {
      mapNote.textContent = "O mapa interativo não carregou. Use a opção para pesquisar a unidade no Google Maps.";
      console.error("Leaflet não foi carregado; o mapa interativo está indisponível.");
      mapSearch?.addEventListener("input", () => {
        const query = normalize(mapSearch.value);
        let visible = 0;
        directoryRows.forEach((row) => {
          const matches = !query || normalize(row.dataset.directorySearch).includes(query);
          row.hidden = !matches;
          if (matches) visible += 1;
        });
        mapNote.textContent = query
          ? `${visible} unidade(s) correspondem à pesquisa.`
          : "O mapa interativo não carregou. Use a opção para pesquisar a unidade no Google Maps.";
      });
      mapButtons.forEach((button) => {
        button.textContent = "Pesquisar";
        button.addEventListener("click", () => {
          if (mapExternalLink) {
            mapExternalLink.href = mapsSearchUrl(button.dataset.mapName || "", button.dataset.mapAddress || "");
            mapExternalLink.hidden = false;
          }
        });
      });
    } else {
      const map = window.L.map(mapFrame).setView(cityCenter, 12);
      let userMarker;
      window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map);

      function makePopup(location) {
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
      }

      fetch(mapFrame.dataset.locationsUrl, { headers: { Accept: "application/json" } })
        .then((response) => {
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          return response.json();
        })
        .then((data) => {
          const mapped = new Map();
            const markersByUnit = new Map();
            const markers = [];
            for (const location of data.locations) {
              if (!mapUnits.has(location.unit_id)) continue;
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
            mapped.set(location.unit_id, { ...location, marker });
            markersByUnit.set(location.unit_id, marker);
            markers.push(marker);
          }

          mapNote.textContent = `${mapped.size} de ${mapUnits.size} unidades aparecem mapeadas no OpenStreetMap.`;
          if (markers.length > 1) {
            map.fitBounds(window.L.featureGroup(markers).getBounds().pad(0.15), { maxZoom: 13 });
          }
          for (const button of mapButtons) {
            const location = mapped.get(button.dataset.mapUnit);
            button.closest("[data-directory-unit]")?.setAttribute("data-map-status", location ? "mapped" : "unmapped");
            if (!location) {
              button.textContent = "Pesquisar";
              continue;
            }
            if (!button.dataset.mapAddress && location.source_address) {
              button.dataset.mapAddress = location.source_address;
              const address = button.previousElementSibling?.querySelector("span");
              if (address) address.textContent = location.source_address;
            }
          }

          function filterDirectory() {
            const query = normalize(mapSearch?.value);
            let visible = 0;
            directoryRows.forEach((row) => {
              const matchesText = !query || normalize(row.dataset.directorySearch).includes(query);
              row.hidden = !matchesText;
              const marker = markersByUnit.get(row.dataset.directoryUnit);
              if (marker) marker.setOpacity(matchesText ? 1 : 0);
              if (!row.hidden) visible += 1;
            });
            if (mapNote && query) {
              mapNote.textContent = `${visible} unidade(s) correspondem à pesquisa. ${mapped.size} têm pino confirmado no OpenStreetMap.`;
            }
            if (query && visible === 1) {
              const matchingRow = Array.from(directoryRows).find((row) => !row.hidden);
              if (matchingRow) showUnit(matchingRow.dataset.directoryUnit);
            }
          }

          function showUnit(unitId) {
            const unit = mapUnits.get(unitId);
            if (!unit) return;

            map.closePopup();
            for (const knownLocation of mapped.values()) knownLocation.marker.closePopup();
            const location = mapped.get(unitId);
            if (location) {
              map.setView([location.latitude, location.longitude], 16);
              location.marker.openPopup();
              mapNote.textContent = `${unit.dataset.mapName} · localização no OpenStreetMap. Endereço da fonte: ${unit.dataset.mapAddress || location.source_address}.`;
              if (mapExternalLink) mapExternalLink.hidden = true;
            } else {
              map.setView(cityCenter, 12);
              mapNote.textContent = `${unit.dataset.mapName} não tem coordenadas confirmadas neste mapa. Consulte o endereço da fonte e pesquise antes de sair.`;
              if (mapExternalLink) {
                mapExternalLink.href = mapsSearchUrl(unit.dataset.mapName || "", unit.dataset.mapAddress || "");
                mapExternalLink.hidden = false;
              }
            }
          }

          mapSearch?.addEventListener("input", filterDirectory);
          mapButtons.forEach((button) => {
            button.addEventListener("click", () => {
              showUnit(button.dataset.mapUnit || "");
              document.querySelector("#unit-map-title")?.scrollIntoView({ behavior: "smooth", block: "start" });
            });
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
        })
        .catch((error) => {
          mapNote.textContent = "Não foi possível carregar as localizações verificadas. Consulte os endereços no diretório.";
          console.error("Falha ao carregar os dados geográficos das unidades.", error);
        });
    }
  }
})();
