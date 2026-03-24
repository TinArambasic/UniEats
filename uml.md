@startuml
left to right direction
actor "Kupac" as K [cite: 53]
actor "Administrator" as A

rectangle "Sustav Web Trgovine" { [cite: 54]
  usecase "Pregled proizvoda" as UC1 [cite: 55]
  usecase "Dodavanje u košaricu" as UC2
  usecase "Plaćanje" as UC3
  usecase "Prijava" as UC4 [cite: 55]
  usecase "Upravljanje zalihama" as UC5
  
  UC3 ..> UC4 : <<include>> [cite: 50]
}

K --> UC1 [cite: 58]
K --> UC2
K --> UC3
A --> UC5
@enduml




@startuml
actor Kupac [cite: 30]
participant "UI Sučelje" as UI [cite: 31]
participant "Narudžba API" as API [cite: 32]
database "Baza podataka" as DB

Kupac -> UI: Odaberi "Kupi" [cite: 33]
UI -> API: Kreiraj narudžbu [cite: 34]
API -> DB: Provjeri dostupnost
alt Proizvod dostupan [cite: 27]
    DB -> API: Potvrda
    API -> UI: Uspješna narudžba [cite: 35]
    UI -> Kupac: Prikaz potvrde
else Nedostupno [cite: 27]
    DB -> API: Greška
    API -> UI: Obavijest o nedostatku
end
@enduml


@startuml
class Korisnik { [cite: 70]
    +String ime
    +String email
    +registrirajSe()
}

class Narudzba { [cite: 71]
    +Date datum
    +String status
}

class Proizvod {
    +String naziv
    +Double cijena
}

Korisnik "1" -- "0..*" Narudzba : kreira > [cite: 72]
Narudzba "1" -- "1..*" Proizvod : sadrži > [cite: 67]
@enduml
