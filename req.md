# Projekt: Narudžbe za menzu/kuhinju (pre-order)
## Članovi tima:
  - Fran Topalić
  - Robert Radman
  - Lovro Roguljić
  - Stjepan Galić
  - Tin Arambašić
## GitHub repozitorij
- Link: https://github.com/TinArambasic/UniEats
- Svi članovi dodani: DA
## User storyji
US-01 Kao student, želim vidjeti sve trenutno dostupne artikle u menzi i naručiti jelo.

US-02 Kao administrator, želim vidjeti sve artikle(Dostupne i nedostupne) te moći raditi CRUD operacije nad svim artiklima(Create, read, update, delete).
## Funkcijski zahtjevi
  - FZ-01 - Sustav mora imati jasno rasclanjene kategorije jela
  - FZ-02 - Sustav mora oznaciti koji su artikli dostupni, a kojih je ponestalo 
  - FZ-03 - Sutav mora prikazati informacije sa studentske iskaznice poput preostale subvencije ili imena studenta
  - FZ-04 - Mogućnost izmjene sastojaka u jelu (npr. maknuti rajčicu ili dodati extra sir)
  - FZ-05 - Sustav mora omogućiti korisniku mogućnost pregleda i uređivanja košarice sve dok narudžba nije primljena
  - FZ-06 - Sustav mora imati prikaz nutritivnih vrijednosti
  - FZ-07 - Sustav mora imati prikaz cijene za svaki proizvod sa subvencijom i bez subvencije
  - FZ-08 - Sustav mora imati prikaz reda čekanja uz mogućnost procijenjenog vremena čekanja
  - FZ-09 - Sustav mora ispisati račun za svaku narudžbu
  - FZ-10 - Mogućnost praćenja statusa narudžbe
## Nefunkcijski zahtjevi
  - NZ-01 - Sustav mora biti kontejniziran i raditi preko dockera
  - NZ-02 - 2 sekunde nakon plaćanja sustav mora zaprimiti narudžbu
  - NZ-03 - Sustav u slucaju pogreske u placanju vraca gresku
  - NZ-04 - Pristup sustavu mogu imati samo autentificirani korisnici (osobe sa studentskim iskaznicama(studenti) i vlasnici restorana (admin))
  - NZ-05 - Sustav mora biti dostupan tijekom radnog vremena
## Taskovi
  - TASK-01 - Implementirati sidebar koji prikazuje vrste jela
  - TASK-02 - Kreirati bazu podataka sa jelima
  - TASK-03 - Implementiranje dohvacanja podataka sa studentske iskaznice preko ISSP Srce API-ja
  - TASK-04 - Napisati test narudžbe
## Raspodjela zadataka
// TODO
