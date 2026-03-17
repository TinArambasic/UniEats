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
  - FZ-01 - Korisnik mora imati uvid svih dostupnih jela
  - FZ-02 - Administrator ima uvid svih dostupnih i nedostupnih artikala
  - FZ-03 - Korisnik ima uvid svojih osobnih podataka poput preostale subvencije ili imena studenta
  - FZ-04 - Korisnik može urediti svoju narudžbu
  - FZ-05 - Administrator može trajno ukloniti artikal iz menija
  - FZ-06 - Korisnik ima prikaz nutritivnih vrijednosti pojedinog artikla
  - FZ-07 - Korisnik može vidjeti cijenu proizvoda
  - FZ-08 - Korisnik može isprazniti košaricu
  - FZ-09 - Administrator može promijeniti cijenu artikla
  - FZ-10 - Korisnik se može prijaviti i odjaviti
## Nefunkcijski zahtjevi
  - NZ-01 - Sustav mora biti kontejniziran i raditi preko dockera
  - NZ-02 - 2 sekunde nakon plaćanja sustav mora zaprimiti narudžbu
  - NZ-03 - Sustav u slucaju pogreske u placanju vraca gresku
  - NZ-04 - Pristup sustavu mogu imati samo autentificirani korisnici (osobe sa studentskim iskaznicama(studenti) i vlasnici restorana (admin))
  - NZ-05 - Sustav mora biti dostupan tijekom radnog vremena
## Taskovi
  - TASK-01 - Implementirati sidebar koji prikazuje vrste jela
  - TASK-02 - Kreirati bazu podataka za sve potrebne entitete (User, Admin, Artikal)
  - TASK-03 - Implementiranje dohvacanja podataka sa studentske iskaznice preko ISSP Srce API-ja
  - TASK-04 - Napisati test narudžbe
  - TASK-05 - Deploy pomoću Dockera
  - TASK-06 - Implementirati restAPI
  - TASK-07 - Napraviti frontend aplikacije
  - TASK-08 - Implementacija backenda
  - TASK-09 - Definirati endpointove
  - TASK-10 - Omogućiti enviroment varijable
## Raspodjela zadataka
  - Fran: 
  - Lovro: 
  - Robert: 
  - Stjepan: 
  - Tin: 
