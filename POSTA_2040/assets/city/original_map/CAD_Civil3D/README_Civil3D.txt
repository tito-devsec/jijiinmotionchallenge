CAD_Civil3D / DXF + LandXML  (nie testowano w Autodesk Civil 3D / not tested in Autodesk Civil 3D)
=====================================================================================================

UKŁAD WSPÓŁRZĘDNYCH / COORDINATE SYSTEM
  Układ lokalny sceny / Local scene system: +proj=tmerc +lat_0=-6.81926 +lon_0=39.29268 +k=1 +x_0=0 +y_0=0 +ellps=WGS84 +units=m +no_defs
  Początek (0,0) = środek sceny: szer. -6.81926, dł. 39.29268 (WGS84). Brak kodu EPSG. / Origin (0,0) = scene centre; no EPSG code.
  Osie / axes: X = easting (wschód / east), Y = northing (północ / north), Z = wysokość / elevation [m].
  Jednostki / units: metry / metres. Pliki CSV: PNEZD (numer, północ, wschód, wysokość, opis).
  Wysokości pochodzą z kafli Terrarium (model terenu, nie geodezyjny pomiar; odniesienie ok. poziomu morza, nie PL-KRON86-NH).
  Elevations come from Terrarium DEM tiles (a terrain model, not a survey; roughly mean sea level, not a national height datum).

PLIKI NA SEKTOR / FILES PER SECTOR  (Tile_X#_Y#)
  .dxf          AutoCAD R12 ASCII. 3DFACE: teren i bryły (warstwy OSM_TERRAIN, OSM_BUILDING_WALLS, OSM_BUILDING_ROOFS, OSM_ROAD_SURFACE,
                OSM_PATH_SURFACE, OSM_RAIL_SURFACE, OSM_BRIDGES, OSM_WATER_SURFACE, ...). Polilinie 3D: OSM_BUILDING_FOOTPRINTS (kontury budynków),
                OSM_ROAD_AXES, OSM_PATH_AXES, OSM_RAIL_AXES (osie, wysokość po terenie lub pomoście), OSM_WATER_OUTLINES, OSM_WATERWAYS.
                Punkty: OSM_TREES. Dane XDATA (aplikacja GENMAP): OSM_ID, NAME. / 3D polylines carry OSM id and name in XDATA.
  _surface.xml  LandXML 1.2: powierzchnia TIN terenu (Surfaces > Surface > Definition surfType="TIN"). Import: Insert > Import > LandXML.
  _points.csv   Punkty terenu PNEZD (alternatywa dla LandXML): Create Points > Import Points, format PNEZD (comma delimited).

UWAGI / NOTES
  - Sektory 2×2 km mają wspólne wierzchołki na granicach; każdy sektor to osobny plik i osobna powierzchnia.
  - Dane OSM są objęte licencją ODbL (© OpenStreetMap contributors): publikacja wymaga atrybucji i share-alike.
  - Wygenerowano w gen-map; format zwalidowano parserami (ezdxf, XML), bez uruchamiania Civil 3D.
  - BEZ GWARANCJI / NO WARRANTY: wynik nie jest pomiarem geodezyjnym ani mapą do celów prawnych; nie używaj go do projektowania, wytyczania, obliczeń kubatur ani dokumentacji wymagającej danych urzędowych (PZGiK, uprawniony geodeta).
    The result is a terrain model, not a survey; do not use it for engineering design, setting out, volume calculations or any work that requires official survey data. Provided "as is".
  - Elevations: Elevation: Terrain Tiles (AWS Open Data, Mapzen Joerd), sources: https://github.com/tilezen/joerd/blob/master/docs/attribution.md
