const world = Globe()
  (document.getElementById('globeViz'))
  .globeImageUrl('//unpkg.com/three-globe/example/img/earth-night.jpg')
  .backgroundImageUrl('//unpkg.com/three-globe/example/img/night-sky.png')
  .polygonCapColor(() => 'rgba(200, 200, 200, 0.6)')
  .polygonSideColor(() => 'rgba(0, 100, 0, 0.1)')
  .polygonStrokeColor(() => '#111');

// URL delle risorse
const COUNTRIES_URL = 'https://raw.githubusercontent.com/vasturiano/globe.gl/master/example/datasets/ne_110m_admin_0_countries.geojson';
const MANIFEST_URL = 'https://raw.githubusercontent.com/bbnss/GloboNews/main/public/news_manifest.json';

let openCluster = null;

// Funzione per chiudere il cluster di icone aperto
const closeOpenCluster = () => {
  if (openCluster) {
    openCluster.querySelectorAll('.spider-item').forEach(item => item.remove());
    openCluster = null;
    world.controls().autoRotate = true;
  }
};

// Evento per chiudere il cluster quando si clicca sul globo
world.onGlobeClick(closeOpenCluster);

// Funzione per popolare il banner delle notizie
const populateTicker = (newsData) => {
    const newsTicker = document.querySelector('.ticker');
    if (newsData && newsData.length > 0) {
        newsTicker.innerHTML = ''; // Pulisce il contenuto
        const sortedNews = [...newsData].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
        
        sortedNews.forEach(newsItem => {
            const itemLink = document.createElement('a');
            itemLink.href = newsItem.link;
            itemLink.target = '_blank';
            itemLink.className = 'ticker-item';

            const icon = document.createElement('img');
            icon.src = newsItem.icon_url;
            icon.className = 'ticker-icon';
            icon.onerror = () => { icon.src = 'https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/assets/Newspaper/3D/newspaper_3d.png'; }; // Fallback

            const title = document.createElement('span');
            title.textContent = newsItem.title;

            itemLink.appendChild(icon);
            itemLink.appendChild(title);
            newsTicker.appendChild(itemLink);
        });
    } else {
        const placeholder = document.createElement('span');
        placeholder.textContent = 'Nessuna notizia disponibile al momento.';
        newsTicker.innerHTML = '';
        newsTicker.appendChild(placeholder);
    }
};

// Funzione principale per caricare e processare i dati
const loadAndProcessData = async () => {
    try {
        const [countries, manifest] = await Promise.all([
            fetch(COUNTRIES_URL).then(res => res.json()),
            fetch(MANIFEST_URL).then(res => res.json())
        ]);

        const GITHUB_RAW_URL_BASE = 'https://raw.githubusercontent.com/bbnss/GloboNews/main/public/';
        const newsPromises = manifest.map(newsFile => fetch(`${GITHUB_RAW_URL_BASE}${newsFile}`).then(res => {
            if (!res.ok) {
                throw new Error(`Failed to fetch ${newsFile}: ${res.statusText}`);
            }
            return res.json();
        }));
        const newsArrays = await Promise.all(newsPromises);
        const allNews = newsArrays.flat();

        // Filtra le notizie per mantenere solo quelle delle ultime 48 ore
        const fortyEightHoursAgo = new Date(Date.now() - 48 * 60 * 60 * 1000);
        const recentNews = allNews.filter(news => new Date(news.timestamp) > fortyEightHoursAgo);
        
        console.log(`Trovate ${allNews.length} notizie totali, ${recentNews.length} sono delle ultime 48 ore.`);

        populateTicker(recentNews);

        const finalNewsData = [];
        const pointGroups = {};
        recentNews.forEach(d => {
            // Riduci la precisione per raggruppare punti molto vicini
            const key = `${d.lat.toFixed(3)},${d.lon.toFixed(3)}`;
            if (!pointGroups[key]) pointGroups[key] = [];
            pointGroups[key].push(d);
        });

        Object.values(pointGroups).forEach(group => {
            if (group.length > 1) {
                const n = group.length;
                // Dimensione decrescente, con un minimo di 15px
                const size = Math.max(15, 40 / Math.sqrt(n));
                // Il raggio del cerchio in gradi di latitudine/longitudine, aumenta con il numero di icone
                const radius = 0.15 * Math.log(n) + 0.05;

                group.forEach((newsItem, index) => {
                    const angle = (index / n) * 2 * Math.PI;
                    // Calcola lo spostamento in gradi. La divisione per Math.cos(...) corregge la distorsione della longitudine vicino ai poli.
                    const lonOffset = radius * Math.cos(angle) / Math.cos(group[0].lat * Math.PI / 180);
                    const latOffset = radius * Math.sin(angle);

                    finalNewsData.push({
                        ...newsItem,
                        lat: group[0].lat + latOffset,
                        lon: group[0].lon + lonOffset,
                        size: size
                    });
                });
            } else {
                // Notizia singola, usa dimensione di default
                finalNewsData.push({ ...group[0], size: 40 });
            }
        });

        world.polygonsData(countries.features)
            .polygonLabel(({ properties: d }) => `<b>${d.ADMIN}</b>`);

        world.htmlElementsData(finalNewsData)
            .htmlLat('lat')
            .htmlLng('lon')
            .htmlElement(d => {
                const el = document.createElement('div');
                const iconUrl = d.icon_url || './icons/news.svg';
                const size = d.size || 40; // Usa la dimensione calcolata o un default

                el.innerHTML = `
                    <img src="${iconUrl}" width="${size}" height="${size}" class="globe-icon" data-base-size="${size}" style="filter: drop-shadow(0 0 3px white); border-radius: 50%;">
                    <div class="tooltip">
                        <div class="tooltip-content">
                            <b>${d.title}</b>
                            <br>
                            <i>Fonte: ${d.source}</i>
                            <small> - ${new Date(d.timestamp).toLocaleString('it-IT')}</small>
                        </div>
                        ${d.description ? `<p class="tooltip-description">${d.description}</p>` : ''}
                    </div>
                `;
                
                el.style.pointerEvents = 'auto';
                el.style.cursor = 'pointer';
                el.onclick = () => window.open(d.link, '_blank');

                const tooltip = el.querySelector('.tooltip');
                el.onmouseover = () => {
                    el.style.zIndex = 100; // Porta l'elemento in primo piano
                    if (tooltip) {
                        tooltip.style.visibility = 'visible';
                        tooltip.style.opacity = 1;
                    }
                    world.controls().autoRotate = false;
                };
                el.onmouseout = () => {
                    el.style.zIndex = 1; // Reimposta l'ordine
                    if (tooltip) {
                        tooltip.style.visibility = 'hidden';
                        tooltip.style.opacity = 0;
                    }
                    world.controls().autoRotate = true;
                };
                return el;
            });

    } catch (error) {
        console.error("Errore durante il caricamento dei dati:", error);
        populateTicker(null);
    }
};

loadAndProcessData();

// Funzione per aggiornare dinamicamente le proprietà del globo in base allo zoom
const updateDynamicProperties = () => {
    const cameraPosition = world.camera().position;
    const globeRadius = world.getGlobeRadius();
    const altitude = cameraPosition.length() - globeRadius;

    // --- Definizione delle soglie e dei valori di default ---
    const activationAltitude = 700; // Altitudine sopra la quale si usa il comportamento di default
    const defaultSpeed = 0.3;
    const minAltitude = 50;  // Altitudine minima per lo zoom massimo

    if (altitude > activationAltitude) {
        // --- STATO DI DEFAULT (ZOOM OUT) ---
        // Se la velocità non è già quella di default, la imposta
        if (world.controls().autoRotateSpeed !== defaultSpeed) {
            world.controls().autoRotateSpeed = defaultSpeed;
        }
        // Reimposta le icone alla loro dimensione di base
        document.querySelectorAll('.globe-icon').forEach(icon => {
            const baseSize = icon.getAttribute('data-base-size');
            if (icon.style.width !== `${baseSize}px`) {
                icon.style.width = `${baseSize}px`;
                icon.style.height = `${baseSize}px`;
            }
        });
    } else {
        // --- STATO DINAMICO (ZOOM IN) ---
        // Calcola il livello di zoom normalizzato (da 0 a 1) all'interno dell'area di ispezione
        const clampedAltitude = Math.max(minAltitude, Math.min(altitude, activationAltitude));
        const zoomLevel = 1 - ((clampedAltitude - minAltitude) / (activationAltitude - minAltitude));

        // 1. Interpola la dimensione delle icone
        const maxSize = 40; // Dimensione target a cui convergono
        document.querySelectorAll('.globe-icon').forEach(icon => {
            const baseSize = parseFloat(icon.getAttribute('data-base-size'));
            const newSize = baseSize + (maxSize - baseSize) * zoomLevel;
            icon.style.width = `${newSize}px`;
            icon.style.height = `${newSize}px`;
        });

        // 2. Interpola la velocità di rotazione
        const minSpeed = 0.05; // Velocità minima allo zoom massimo
        const newSpeed = defaultSpeed - (defaultSpeed - minSpeed) * zoomLevel;
        world.controls().autoRotateSpeed = newSpeed;
    }
};

// Aggiungi l'ascoltatore per l'evento di cambio visuale (zoom, pan)
world.controls().addEventListener('change', updateDynamicProperties);

world.controls().autoRotate = true;
world.controls().autoRotateSpeed = 0.3;
window.addEventListener('resize', () => {
    world.width(window.innerWidth);
    world.height(window.innerHeight);
});
world.width(window.innerWidth).height(window.innerHeight);
