"""Explicit environmental publication identities, verified from BIP attachments.

No fuzzy project matching. Each tuple is a reviewed same-project identity from
project wording + location/parcel list, NOT a truncated case-number heuristic.
Some BIP files contain contradictory case numbers; preserve those as facts.
Region IDs are exact official ULDK identities; malformed 001/011 stay unmapped.
Corporate investors below are allowlisted facts, never personal representatives.
"""

# (publication IDs oldest first, own factual title, corporate investor, category,
# locality, address, verified region identity, literal parcels, investor document)
ENVIRONMENT = [
    (['95209','95807','95924','96019','96063'], 'Magazyn energii — Pogroszew Kolonia, działka 147/8', 'Grenergy Polska Sp. z o.o.', 'energia', 'Pogroszew Kolonia', '', '143206_5.0017', ['147/8'], '202997'),
    (['95445','95482','96020'], 'Zespół mieszkaniowy — PGR Szeligi, działka 6 i część działki 7', 'PROFBUD URSYNÓW', 'mieszkalnictwo', 'Szeligi', 'ul. Szeligowska', '143206_5.0031', ['6','7'], '202259'),
    (['95263','95449','95657','95671','95921'], 'Studnia nr 1 dla campusu DATA4 — Jawczyce, działka 143/11', 'DATA4 POLAND Sp. z o.o.', 'gospodarka wodna', 'Jawczyce', '', '143206_5.0005', ['143/11'], '201665'),
    (['95918'], 'Zmiana decyzji środowiskowej — ul. Kapucka', None, 'drogi', 'Ożarów Mazowiecki', 'ul. Kapucka', None, [], None),
    (['95795','95917'], 'Kanalizacja sanitarna — Jawczyce i Konotopa', 'Gmina Ożarów Mazowiecki', 'kanalizacja', 'Jawczyce; Konotopa', '', None, [], '203179'),
    (['95655','95808'], 'Hala magazynowo-usługowa AJS PARTS — Jawczyce', 'AJS PARTS Sp. z o.o., Sp.k.', 'magazyny i produkcja', 'Jawczyce', '', '143206_5.0005', ['44/2','45/5','46/8','47/5','49/10','49/11'], '202753'),
    (['95273','95793'], 'Regulacja Kanału Ożarowskiego w ramach budowy ul. Kapuckiej', None, 'gospodarka wodna', 'Ożarów Mazowiecki', 'ul. Kapucka', None, [], None),
    (['95435','95538','95670','95752'], 'Rozbudowa zespołu serwerowni DATA4 — Jawczyce', 'DATA4 POLAND Sp. z o.o.', 'centra danych', 'Jawczyce', 'ul. Przyparkowa 21', None, [], '202207'),
    (['95723'], 'Magazyn energii — Pogroszew, działki 129/6 i 130/1', 'HEP1 Sp. z o.o.', 'energia', 'Pogroszew', '', '143206_5.0016', ['129/6','130/1'], '202866'),
    (['95247','95678'], 'Hale magazynowo-produkcyjno-usługowe — działki 255–259, obręb literalny 001', 'Commercial Point Sp. z o.o.', 'magazyny i produkcja', '', '', None, [], '201628'),
    (['95285','95676'], 'Ujęcie wód podziemnych — Piotrkówek Mały, PGR Strzykuły, działka 9/7', None, 'gospodarka wodna', 'Piotrkówek Mały', '', '143206_5.0030', ['9/7'], None),
    (['95291','95675'], 'Lakiernia w budynku serwisu samochodowego — Wieruchów, działka 59/2', 'AUTO GT Sp. z o.o.', 'usługi', 'Wieruchów', '', '143206_5.0024', ['59/2'], '201822'),
    (['95651'], 'Zmiana decyzji — instalacja demontażu pojazdów, Konotopa', None, 'gospodarka odpadami', 'Konotopa', 'ul. Inwestycyjna', '143206_5.0007', ['155/5','156'], None),
    (['95564'], 'Zespół serwerowni LF10 — Jawczyce, działki 147/2, 147/3 i 148/8', 'LF10 Sp. z o.o.', 'centra danych', 'Jawczyce', '', '143206_5.0005', ['147/2','147/3','148/8'], '202627'),
    (['95477'], 'Rozbudowa ul. Wygodnej i odcinka ul. Kapuckiej', 'Gmina Ożarów Mazowiecki', 'drogi', 'Kaputy', 'ul. Wygodna; ul. Kapucka; ul. Sochaczewska', None, [], '202315'),
    (['95378'], 'Zespół domów jednorodzinnych — PGR Kręczki Kaputy', 'Strus Development Sp. z o.o.', 'mieszkalnictwo', 'Kręczki Kaputy', 'ul. Sochaczewska', '143206_5.0027', [], '202103'),
    (['95357'], 'Hale magazynowo-usługowe — obręb literalny 011', None, 'magazyny i produkcja', '', '', None, [], None),
    (['95353'], 'Zespół 180 domów i 5 budynków usługowych — PGR Strzykuły', None, 'mieszkalnictwo', 'PGR Strzykuły', '', '143206_5.0030', [], None),
    (['95091'], 'Data center — Płochocin, obręb 0019', None, 'centra danych', 'Płochocin', '', '143206_5.0019', ['197/5','198/5','198/6','200/5','202/4','203/4','204/4','205/4','206/5','207/4','208/7','210/4','211/2','212/4','213/5','214/5','215/4','217/9','218/3'], None),
]

# Verified cadastral names, exact GetRegionById + expected municipality required
# AGAIN at every geometry generation. This list is not a geocoder.
REGIONS = {
    '143206_5.0005': 'Jawczyce', '143206_5.0007': 'Konotopa',
    '143206_5.0016': 'Pogroszew', '143206_5.0017': 'Pogroszew Kol.',
    '143206_5.0019': 'Płochocin', '143206_5.0024': 'Wieruchów',
    '143206_5.0027': 'PGR Kręczki Kaputy', '143206_5.0030': 'PGR Strzykuły',
    '143206_5.0031': 'PGR Szeligi', '143206_4.0003': '0003',
}

AURA = 'https://aura-nova.pl/wp-content/uploads/2025/11/Prospekt-Informacyjny_Aura-Nova-I.pdf'
HILLWOOD = 'https://www.hillwood.pl/nieruchomosci/hillwood-ozarow-iii/'
HOME = 'https://homepremium.pl/wp-content/uploads/2025/09/Prospekt-informacyjny-02.09.2025-6.pdf'
CPK_API = 'https://bip.ozarow-mazowiecki.pl/api/articles/95745'
PWZ = 'https://pwz.pl/news/uwaga-roboty-drogowe-w-gminie-ozarow-mazowiecki'
A2 = 'https://www.gov.pl/web/uw-mazowiecki/trzeci-pas-na-a2--wazne-decyzje-wojewody'
GAS = 'https://bip.ozarow-mazowiecki.pl/m,20115,planowana-budowa-gazociagu-rembelszczyzna-mory-wola-karczewska.html'
FE_PAGE = 'https://funduszeeuropejskie.gov.pl/raporty-i-analizy/lista-projektow-realizowanych-z-funduszy-europejskich-w-polsce-w-latach-2021-2027'

# Own concise factual summaries of the actual 2026-09-30 workbook descriptions.
# No copied description paragraphs, claims of completed work or derived points.
FE_SUMMARIES = {
    'FEMA.01.01-IP.01-02BW/24': 'Prace B+R nad sterowaniem termicznym przekształcaniem odpadów z wykorzystaniem AI.',
    'FEMA.02.06-IP.01-01UR/24': 'Doradztwo i ekoprojektowanie zbiorników w ramach transformacji firmy ku gospodarce obiegu zamkniętego.',
    'FEMA.03.02-IP.01-02AF/24': 'Zakup autobusów elektrycznych oraz infrastruktury ładowania dla przewozów publicznych.',
    'FEMA.03.02-IP.01-02JI/24': 'Rozwój gminnej infrastruktury rowerowej wzdłuż DK92 przez siedem miejscowości.',
    'FEMA.03.02-IP.01-07EZ/24': 'Rozbudowa floty autobusów elektrycznych dla regionalnego transportu publicznego.',
    'FEMA.07.01-IP.01-02ZF/24': 'Nowe miejsca przedszkolne, zajęcia dla dzieci i wsparcie kwalifikacji nauczycieli.',
    'FEMA.07.05-IP.01-08BL/25': 'Rozwijanie kompetencji cyfrowych dorosłych zagrożonych wykluczeniem cyfrowym.',
    'FEMA.07.05-IP.01-08IA/25': 'Szkolenia cyfrowe dla dorosłych o niskich kompetencjach w obszarze LGD.',
    'FEMA.08.01-IP.01-082Q/25': 'Indywidualne wsparcie reintegracji społecznej i zawodowej osób pozostających bez zatrudnienia.',
    'FEMA.08.01-IP.01-089X/25': 'Aktywizacja osób biernych zawodowo oraz zagrożonych ubóstwem lub wykluczeniem społecznym.',
    'FEMA.08.01-IP.01-08B2/25': 'Partnerskie wsparcie integracji społeczno-zawodowej osób pozostających bez zatrudnienia.',
    'FEMA.08.01-IP.01-08J0/25': 'Indywidualne ścieżki rozwoju i aktywizacja zawodowa osób zagrożonych wykluczeniem.',
    'FENG.01.01-IP.01-1014/23': 'Druga faza badań nad biologicznym lekiem dla nieswoistych stanów zapalnych jelit.',
    'FENG.01.01-IP.01-A0MR/24': 'Prace B+R nad fotoniką scaloną do komunikacji optycznej w wolnej przestrzeni.',
    'FENG.01.01-IP.01-A0QS/24': 'Rozwój procesu wytwarzania biopodobnego przeciwciała do terapii chorób autoimmunologicznych.',
    'FENG.01.01-IP.02-1216/23': 'Prace B+R nad detektorami kaskadowymi i modułami detekcji długofalowej podczerwieni.',
    'FENG.02.10-IP.01-0005/23': 'HyperPIC: rozwój technologii i infrastruktury wytwarzania układów fotonicznych dla średniej podczerwieni.',
    'FENG.02.25-IP.02-0154/24': 'Promocja eksportowa VIGO poprzez targi, misje gospodarcze i kampanię na rynku niemieckim.',
    'FENG.02.25-IP.02-0188/25': 'Promocja eksportowa VIGO na targach, misjach gospodarczych i w kampaniach w USA.',
    'FENG.05.01-IP.01-0003/25': 'Rozwój procesu produkcji biopodobnego przeciwciała monoklonalnego w skali komercyjnej.',
    'FENG.05.01-IP.01-002E/25': 'Prace nad detektorami i modułami średniej podczerwieni przystosowanymi do montażu powierzchniowego.',
    'FENX.01.04-IW.01-0015/23': 'Rozbudowa gminnego punktu selektywnego zbierania odpadów komunalnych.',
    'FENX.02.03-IW.02-0006/23': 'Budowa gazociągu Rembelszczyzna–Mory dla aglomeracji warszawskiej; cały projekt obejmuje około 28,5 km.',
    'FERC.01.01-IP.01-0021/23': 'Rozwój sieci NGA i dostępu do szybkich usług łączności na obszarach wykluczenia cyfrowego.',
}
