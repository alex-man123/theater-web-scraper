# Exemple de prompturi de sprijin AI

Colecție de **exemple** de prompturi prin care un student poate cere ajutor punctual la proiectul Odeon:
explicații, structură, indicii sau verificări — nu realizarea completă a aplicației.
Exemplele nu reprezintă un istoric real al solicitărilor.

---

### 1. Organizarea folderelor
**Prompt:** „Facem un crawler pentru Teatrul Odeon în Python, cu MySQL și o interfață Flask. Propune-mi o structură de foldere care separă descărcarea paginilor, parsarea, accesul la baza de date și afișarea, și explică pe scurt rolul fiecărui folder. Nu scrie codul.”
**Scop educațional:** studentul învață să separe responsabilitățile înainte de a scrie cod.

### 2. Schelet cu funcții neimplementate
**Prompt:** „Scrie-mi doar semnăturile funcțiilor pentru modulul care parsează pagina unui spectacol Odeon (titlu, durată, distribuție, afiș), cu docstring-uri și `raise NotImplementedError`. Vreau să le implementez eu.”
**Scop educațional:** oferă un punct de plecare clar, lăsând implementarea în sarcina studentului.

### 3. Crawler vs. scraper
**Prompt:** „Explică-mi diferența dintre crawling, scraping și parsing folosind exemplul concret al site-ului Odeon: pagina /stagiune/ și paginile /spectacol/<nume>/. Care parte a proiectului nostru face fiecare lucru?”
**Scop educațional:** clarifică noțiunile de bază din curs pe un caz real.

### 4. Relația dintre shows și performances
**Prompt:** „De ce avem două tabele, shows și performances, legate prin cheie externă? Dă-mi un exemplu cu Macbeth jucat de trei ori și spune-mi ce s-ar strica dacă am ține totul într-un singur tabel.”
**Scop educațional:** înțelegerea normalizării și a relației unu-la-mulți.

### 5. Înțelegerea selectorilor HTML
**Prompt:** „Am acest fragment HTML din pagina unui spectacol Odeon: [fragment]. Ce selector CSS ar alege afișul și de ce `img.vc_single_image-img` ar putea prinde și codul QR? Dă-mi indicii, nu soluția completă.”
**Scop educațional:** exersează citirea structurii HTML și alegerea unor selectori robuști.

### 6. Transformarea distribuției în JSON
**Prompt:** „Distribuția apare ca «Doamna Mullerova: Dorina Lazăr / Dana Voicu». Cum ar trebui reprezentată în cast_json conform exemplului din PDF? Ce cazuri-limită ar trebui să am în vedere (actori alternativi, roluri multiple)?”
**Scop educațional:** transformarea unui text semi-structurat într-o structură de date bine definită.

### 7. Normalizarea datelor și orelor
**Prompt:** „Programul afișează «dum 22 nov.» și «19:00», fără an. Ce strategii există pentru a deduce anul? De ce ar trebui să salvez ora în UTC și ce se întâmplă la trecerea la ora de vară?”
**Scop educațional:** înțelegerea problemelor reale legate de date calendaristice și fusuri orare.

### 8. Evitarea duplicatelor
**Prompt:** „Dacă rulez crawlerul de două ori, cum mă asigur că reprezentațiile nu se dublează? Dă-mi 2–3 idei de chei de deduplicare și avantajele/dezavantajele fiecăreia, fără cod complet.”
**Scop educațional:** gândirea în termeni de identitate a unei înregistrări.

### 9. Actualizarea înregistrărilor
**Prompt:** „Explică-mi diferența dintre a șterge și reinsera datele la fiecare rulare și a face un «upsert» care actualizează doar câmpurile modificate. Ce se întâmplă cu updated_at și cu o reprezentație care dispare din program?”
**Scop educațional:** înțelegerea strategiilor de sincronizare cu o sursă externă.

### 10. Interpretarea unei erori
**Prompt:** „Primesc `UnicodeEncodeError: 'charmap' codec can't encode character 'ă'` când afișez titlurile în consola Windows. Ce înseamnă eroarea și unde ar putea fi problema: în date, în baza de date sau în consolă?”
**Scop educațional:** dezvoltă capacitatea de a diagnostica o eroare pornind de la mesajul ei.

### 11. Revizuirea unui fragment de cod
**Prompt:** „Uită-te la funcția mea care descarcă o pagină: [cod]. Respectă robots.txt și o pauză între cereri? Ce se întâmplă la un răspuns 429 cu Retry-After? Spune-mi problemele, nu rescrie funcția.”
**Scop educațional:** primirea unui feedback țintit, cu corectarea făcută de student.

### 12. Propunerea unor cazuri de test
**Prompt:** „Ce cazuri de test ar trebui să am pentru parserul de program al teatrului Odeon? Gândește-te la câmpuri lipsă, reprogramări, ore la miezul nopții și titluri care diferă ușor de cele din repertoriu.”
**Scop educațional:** învățarea gândirii orientate spre cazuri-limită și testare.

### 13. Interfața pe mobil
**Prompt:** „Pagina /schedule arată bine pe desktop, dar pe telefon tabelul iese din ecran. Ce variante de afișare responsive îmi recomanzi pentru o listă de reprezentații (dată, oră, spectacol, sală)? Explică ideea de CSS, nu tot fișierul.”
**Scop educațional:** principii de design responsive aplicate pe interfața proiectului.

### 14. Verificarea acoperirii cerințelor
**Prompt:** „Iată lista cerințelor din PDF și lista funcționalităților pe care le avem: [liste]. Ce cerințe obligatorii lipsesc sau nu sunt încă verificate? Separă obligatoriu de opțional.”
**Scop educațional:** verificarea sistematică a proiectului față de enunț.

### 15. Organizarea documentației
**Prompt:** „Ce secțiuni ar trebui să conțină README-ul proiectului nostru de crawler, ca un coleg să poată instala, rula și testa aplicația fără ajutor? Propune doar cuprinsul și ce ar trebui explicat în fiecare secțiune.”
**Scop educațional:** structurarea documentației tehnice pentru un cititor nou.
