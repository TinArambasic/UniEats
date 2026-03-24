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
 
- uloga Student
- sudionik "Frontend" kao FE
- sudionik "REST API" kao API
- sudionik "Baza podataka" kao DB
 
Student -> FE : otvori meni
- FE -> API : GET /api/artikli
- API -> DB : SELECT dostupni artikli
- DB --> API : [lista artikala]
- API --> FE : 200 OK + jela
- FE --> Student : prikaži meni
 
alt košarica nije prazna
  - Student -> FE : dodaj u košaricu
  - Student -> FE : potvrdi narudžbu
  - FE -> API : POST /api/narudzba
  - API -> DB : INSERT narudžba
  - DB --> API : [OK]
  - API --> FE : 201 Created
  - FE --> Student : narudžba zaprimljena
else košarica prazna
  - FE --> Student : upozori: košarica je prazna
end
 
@enduml


usecase
@startuml
left to right direction

actor "Student (Korisnik)" as student
actor "Administrator" as admin

rectangle "UniEats Sustav"{
    usecase "Prijava i odjava" as UC_Prijava
    
    usecase "Pregled dostupnih jela" as UC_PregledJela
    usecase "Pregled nutritivnih vrijednosti" as UC_Nutrijenti
    usecase "Pregled cijene" as UC_Cijena
    
    usecase "Naručivanje jela" as UC_Narudzba
    usecase "Uređivanje narudžbe" as UC_Uredi
    usecase "Pražnjenje košarice" as UC_Prazni
    
    usecase "Uvid u osobne podatke" as UC_Podaci

    usecase "Upravljanje artiklima (CRUD)" as UC_CRUD
    usecase "Promjena cijene artikla" as UC_PromjenaCijene
    usecase "Trajno uklanjanje artikla" as UC_Uklanjanje
    usecase "Pregled svih artikala" as UC_SviArtikli
}

' student relacije
student --> UC_Prijava
student --> UC_PregledJela
student --> UC_Narudzba
student --> UC_Podaci

' admin relacije
admin --> UC_Prijava
admin --> UC_CRUD
admin --> UC_SviArtikli

' include i extend relacije 
UC_Narudzba ..> UC_Prijava : <<include>>
UC_CRUD ..> UC_Prijava : <<include>>

UC_PregledJela <.. UC_Nutrijenti : <<extend>>
UC_PregledJela <.. UC_Cijena : <<extend>>

UC_Narudzba <.. UC_Uredi : <<extend>>
UC_Narudzba <.. UC_Prazni : <<extend>>

UC_CRUD <.. UC_PromjenaCijene : <<extend>>
UC_CRUD <.. UC_Uklanjanje : <<extend>>

@enduml

