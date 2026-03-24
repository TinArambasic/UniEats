@startuml

class Korisnik {
  - id: int
  - ime: String
  - prezime: String
  - iksicaBroj: String
}

class Menza {
  - id: int
  - naziv: String
  - lokacija: String
}

class Jelo {
  - id: int
  - naziv: String
  - cijena: double
  - kategorija: String
  - dostupno: boolean
}

class Narudzba {
  - id: int
  - datumVrijeme: DateTime
  - narudzbaPreuzeta: boolean
  - ukupnaCijena: double
}

class StavkaNarudzbe {
  - kolicina: int
  - napomena: String
}

' Veze s multiplicitetom
Korisnik "1" -- "0..*" Narudzba : kreira >
Menza "1" -- "0..*" Jelo : nudi >
Narudzba "0..*" -- "1" Menza : se preuzima u >
Narudzba "1" *-- "1..*" StavkaNarudzbe : sadrži >
StavkaNarudzbe "0..*" -- "1" Jelo : odnosi se na >

@enduml







### Opis
 
Scenarij prikazuje tok narudžbe jela od strane studenta. Student otvara meni, frontend dohvaća dostupna jela s REST API-ja, a API ih čita iz baze podataka. Blok alt pokriva dva slučaja:
- ako košarica **nije prazna** — student potvrđuje narudžbu, API je sprema u bazu i vraća potvrdu,
- ako je košarica **prazna** — frontend prikazuje upozorenje studentu.
 
Sukladno nefunkcijskom zahtjevu NZ-02, sustav mora zaprimiti narudžbu unutar 2 sekunde od plaćanja.
 
@startuml
 
actor Student
participant "Frontend" as FE
participant "REST API" as API
participant "Baza podataka" as DB
 
Student -> FE : otvori meni
FE -> API : GET /api/artikli
API -> DB : SELECT dostupni artikli
DB --> API : [lista artikala]
API --> FE : 200 OK + jela
FE --> Student : prikaži meni
 
alt košarica nije prazna
  Student -> FE : dodaj u košaricu
  Student -> FE : potvrdi narudžbu
  FE -> API : POST /api/narudzba
  API -> DB : INSERT narudžba
  DB --> API : [OK]
  API --> FE : 201 Created
  FE --> Student : narudžba zaprimljena
else košarica prazna
  FE --> Student : upozori: košarica je prazna
end
 
@enduml
