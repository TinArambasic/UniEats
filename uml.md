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
