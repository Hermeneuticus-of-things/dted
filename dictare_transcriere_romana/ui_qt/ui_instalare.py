"""Ecranul „Instalare” PySide6: arată starea instalării.

Înlocuiește ``ui_instalare.py`` (Tkinter, asistentul de instalare în 10 pași).
Aici, în programul care deja rulează, arătăm doar starea, fără acțiuni care
șterg sau schimbă ceva: versiunea, componentele și o verificare completă.
"""

from __future__ import annotations

import json
import threading

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from .. import actualizare, cai, instalare, libreoffice
from ..constante import NUME_AFISAT, NUME_SCURT, VERSIUNE_COMPLETA
from . import comun
from .comun import Buton, anunta, fonturi, seteaza_rol


class FereastraInstalare(QWidget):
    """Verificarea stării instalării (numai citire)."""

    def __init__(self, parinte: QWidget, aplicatie):
        super().__init__(parinte)
        self.aplicatie = aplicatie
        self.coada = comun.CoadaUI(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(10)

        titlu = QLabel("Instalare și actualizări")
        titlu.setFont(fonturi("titlu"))
        layout.addWidget(titlu)

        versiune = QLabel(f"{NUME_AFISAT} ({NUME_SCURT}) — versiunea {VERSIUNE_COMPLETA}")
        versiune.setFont(fonturi("baza"))
        versiune.setWordWrap(True)
        layout.addWidget(versiune)

        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 12, 16, 12)
        cl.setSpacing(6)
        et = QLabel("Starea componentelor")
        et.setFont(fonturi("buton"))
        cl.addWidget(et)

        self.et_model = self._rand_componenta(cl, "Modelul de transcriere (Whisper)")
        self.et_scris = self._rand_componenta(cl, "Programul de scris (LibreOffice)")

        layout.addWidget(card)

        self.et_detalii = QLabel("")
        self.et_detalii.setFont(fonturi("baza"))
        self.et_detalii.setWordWrap(True)
        layout.addWidget(self.et_detalii)

        rand = QHBoxLayout()
        rand.setSpacing(8)
        self.btn_verifica = Buton(self, "Verifică din nou", self._verifica, fel="principal", latime=220, inaltime=40)
        rand.addWidget(self.btn_verifica)
        rand.addStretch(1)
        layout.addLayout(rand)

        # Actualizările (N-2): pornesc DOAR la buton, niciodată singure.
        card_act = QFrame()
        card_act.setObjectName("card")
        ca = QVBoxLayout(card_act)
        ca.setContentsMargins(16, 12, 16, 12)
        ca.setSpacing(6)
        et_act = QLabel("Actualizări pe componente")
        et_act.setFont(fonturi("buton"))
        ca.addWidget(et_act)
        et_act_detaliu = QLabel(
            "Programul nu caută și nu descarcă nimic singur. La apăsarea butonului "
            "compară versiunile componentelor (program, model) cu lista oficială; "
            "se descarcă doar ce schimbi tu, cu sumă verificată și copie de siguranță."
        )
        et_act_detaliu.setFont(fonturi("mica"))
        seteaza_rol(et_act_detaliu, "secundar")
        et_act_detaliu.setWordWrap(True)
        ca.addWidget(et_act_detaliu)
        rand_act = QHBoxLayout()
        rand_act.setSpacing(8)
        self.btn_actualizari = Buton(
            self, "Caută actualizări (internet)", self._cauta_actualizari, fel="principal", latime=250, inaltime=40
        )
        self.btn_revino = Buton(
            self, "Revino la versiunea anterioară", self._revino_actualizare, latime=270, inaltime=40
        )
        rand_act.addWidget(self.btn_actualizari)
        rand_act.addWidget(self.btn_revino)
        rand_act.addStretch(1)
        ca.addLayout(rand_act)
        layout.addWidget(card_act)

        # Curățenie (cerința 3): modelul vechi de PyTorch, dacă mai există pe disc.
        self._cale_model_vechi = cai.director_model() / "large-v3-turbo.pt"
        card_curat = QFrame()
        card_curat.setObjectName("card")
        cc = QVBoxLayout(card_curat)
        cc.setContentsMargins(16, 12, 16, 12)
        cc.setSpacing(6)
        et_curat = QLabel("Curățenie")
        et_curat.setFont(fonturi("buton"))
        cc.addWidget(et_curat)
        self.et_model_vechi = QLabel(
            "Modelul vechi (large-v3-turbo.pt, ~1,6 GB) mai ocupă loc pe disc, "
            "deși programul folosește modelul nou. Îl poți șterge de aici."
            if self._cale_model_vechi.exists()
            else "Modelul vechi de PyTorch nu mai există pe disc: totul e în ordine."
        )
        self.et_model_vechi.setFont(fonturi("mica"))
        seteaza_rol(self.et_model_vechi, "secundar")
        self.et_model_vechi.setWordWrap(True)
        cc.addWidget(self.et_model_vechi)
        self.btn_sterge_vechi = Buton(
            self,
            "Șterge modelul vechi (eliberează ~1,6 GB)",
            self._sterge_model_vechi,
            latime=320,
            inaltime=40,
        )
        self.btn_sterge_vechi.setVisible(self._cale_model_vechi.exists())
        cc.addWidget(self.btn_sterge_vechi)
        layout.addWidget(card_curat)

        layout.addStretch(1)

        self._verifica()

    @staticmethod
    def _rand_componenta(col: QVBoxLayout, nume: str) -> QLabel:
        rand = QHBoxLayout()
        lab = QLabel(nume)
        lab.setFont(fonturi("baza"))
        rand.addWidget(lab, 1)
        stare = QLabel("se verifică…")
        stare.setFont(fonturi("baza"))
        seteaza_rol(stare, "secundar")
        rand.addWidget(stare)
        col.addLayout(rand)
        return stare

    def _verifica(self) -> None:
        self.btn_verifica.setEnabled(False)
        for eticheta in (self.et_model, self.et_scris):
            eticheta.setText("se verifică…")
            seteaza_rol(eticheta, "secundar")
        self.et_detalii.setText("")

        def lucru() -> None:
            model_ok = cai.fisier_model().exists()
            try:
                scris_ok = libreoffice.stare().gasit
            except Exception:
                scris_ok = False
            try:
                probleme = instalare.verifica_instalare()
            except Exception as exc:
                probleme = [f"Verificarea completă a eșuat: {exc}"]
            self.coada.trimite(self._dupa_verificare, model_ok, scris_ok, probleme)

        threading.Thread(target=lucru, name="verificare-instalare", daemon=True).start()

    def _dupa_verificare(self, model_ok: bool, scris_ok: bool, probleme: list[str]) -> None:
        self.btn_verifica.setEnabled(True)
        self._pune(self.et_model, model_ok)
        self._pune(self.et_scris, scris_ok)
        if not probleme:
            self.et_detalii.setText("Totul este în regulă: programul are tot ce îi trebuie.")
            seteaza_rol(self.et_detalii, "verde")
        else:
            self.et_detalii.setText("• " + "\n• ".join(probleme))
            seteaza_rol(self.et_detalii, "pericol")

    @staticmethod
    def _pune(eticheta: QLabel, ok: bool) -> None:
        eticheta.setText(("✔  instalat" if ok else "✘  lipsește"))
        seteaza_rol(eticheta, "verde" if ok else "pericol")

    def _sterge_model_vechi(self) -> None:
        """Cerința 3: șterge large-v3-turbo.pt, cu confirmare (operație unică)."""
        cale = self._cale_model_vechi
        try:
            gabarit = cale.stat().st_size / (1024 * 1024 * 1024)
        except OSError:
            gabarit = 1.5
        raspuns = QMessageBox.question(
            self,
            "Șterg modelul vechi?",
            f"Se șterge definitiv {cale.name} ({gabarit:.1f} GB).\n\n"
            "Programul folosește modelul nou (CT2), deci dictarea și transcrierea "
            "merg în continuare. Modelul vechi NU se poate readuce decât reinstalând.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if raspuns != QMessageBox.StandardButton.Yes:
            return
        try:
            cale.unlink(missing_ok=True)
        except OSError as exc:
            self.et_model_vechi.setText(f"✘ Nu am putut șterge fișierul: {exc}")
            seteaza_rol(self.et_model_vechi, "pericol")
            return
        self.btn_sterge_vechi.setVisible(False)
        self.et_model_vechi.setText("✔ Modelul vechi a fost șters. Locul e eliberat.")
        seteaza_rol(self.et_model_vechi, "verde")

    # ------------------------------------------------------------- actualizări (N-2)

    def _cauta_actualizari(self) -> None:
        """Caută actualizări DOAR la buton (0.8.2): compară versiunile cu manifestul."""
        from .. import constante

        self.btn_actualizari.setEnabled(False)
        self.btn_revino.setEnabled(False)
        self.et_detalii.setText("Se caută actualizări pe internet…")
        seteaza_rol(self.et_detalii, "secundar")

        def lucru() -> None:
            from .. import actualizare as act

            # Sincronizează versiunea rulată acum înainte de comparare.
            act.sincronizeaza_versiuni_curente()
            temporar = act.fisier_versiuni().parent / "manifest-descarcat.json"
            if not act.descarca(constante.URL_MANIFEST_ACTUALIZARI, temporar):
                self.coada.trimite(self._eroare_cautare)
                return
            try:
                manifest = json.loads(temporar.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                temporar.unlink(missing_ok=True)
                self.coada.trimite(self._eroare_cautare)
                return
            temporar.unlink(missing_ok=True)
            schimbari = act.ce_s_a_schimbat(manifest)
            self.coada.trimite(self._dupa_cautare, schimbari, manifest)

        threading.Thread(target=lucru, name="cauta-actualizari", daemon=True).start()

    def _eroare_cautare(self) -> None:
        self.btn_actualizari.setEnabled(True)
        self.btn_revino.setEnabled(True)
        self.et_detalii.setText(
            "Nu am putut căuta actualizări: fie nu e internet, fie lista oficială nu răspunde.\n"
            "Nimic nu s-a schimbat la instalare — poți folosi programul în continuare."
        )
        seteaza_rol(self.et_detalii, "pericol")

    def _dupa_cautare(self, schimbari: list, manifest: dict) -> None:
        from .. import actualizare as act

        self.btn_actualizari.setEnabled(True)
        self.btn_revino.setEnabled(True)
        if not schimbari:
            self.et_detalii.setText("Ești la zi: toate componentele au ultima versiune.")
            seteaza_rol(self.et_detalii, "verde")
            return
        descarcabile = [
            s for s in schimbari if str((manifest or {}).get(s.nume, {}).get("url", "")).strip()
        ]
        texte = [f"• {s.eticheta}" for s in schimbari]
        confirmate = []
        for schimbare in descarcabile:
            marime_txt = (
                f" ({schimbare.dimensiune / (1024 * 1024):.1f} MB)"
                if getattr(schimbare, "dimensiune", 0) > 0
                else ""
            )
            raspuns = QMessageBox.question(
                self,
                f"Actualizez «{schimbare.nume}»?",
                f"{schimbare.eticheta}{marime_txt}\n\n"
                "Descarc și înlocuiesc doar această componentă?\n"
                "Cea veche se păstrează și poți reveni oricând la ea.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if raspuns == QMessageBox.StandardButton.Yes:
                confirmate.append(schimbare)
        if not confirmate:
            self.et_detalii.setText(
                "Update-uri disponibile:\n" + "\n".join(texte) + "\n\nNimic nu s-a descărcat."
            )
            seteaza_rol(self.et_detalii, "secundar")
            return
        self._descarca_si_aplica(confirmate, manifest)

    def _descarca_si_aplica(self, schimbari: list, manifest: dict) -> None:
        from .. import actualizare as act

        self.btn_actualizari.setEnabled(False)
        self.btn_revino.setEnabled(False)

        def progres(primiti: int, total: int) -> None:
            if total > 0:
                self.coada.trimite(
                    self._text_progres, f"Se descarcă… {primiti / total * 100:.0f}%"
                )

        def lucru() -> None:
            rapoarte: list[str] = []
            for schimbare in schimbari:
                meta = (manifest or {}).get(schimbare.nume, {})
                pachet = cai.director_descarcari() / f"{schimbare.nume}-{schimbare.noua}"
                ok = act.descarca(
                    str(meta.get("url", "")),
                    pachet,
                    str(meta.get("sha256", "")),
                    progres=progres,
                )
                if not ok:
                    rapoarte.append(f"✘ {schimbare.nume}: descărcarea a eșuat (sumă sau rețea)")
                    continue
                try:
                    act.aplica(schimbare.nume, schimbare.noua, pachet)
                    rapoarte.append(f"✔ {schimbare.eticheta} — instalat")
                except Exception as exc:
                    rapoarte.append(f"✘ {schimbare.nume}: instalarea a eșuat ({exc})")
            self.coada.trimite(self._dupa_aplicare, rapoarte)

        threading.Thread(target=lucru, name="aplica-actualizari", daemon=True).start()

    def _text_progres(self, text: str) -> None:
        self.et_detalii.setText(text)
        seteaza_rol(self.et_detalii, "secundar")

    def _dupa_aplicare(self, rapoarte: list[str]) -> None:
        self.btn_actualizari.setEnabled(True)
        self.btn_revino.setEnabled(True)
        self.et_detalii.setText("\n".join(rapoarte))
        reusit = any("✔" in r for r in rapoarte)
        seteaza_rol(self.et_detalii, "verde" if reusit else "pericol")
        self._verifica()
        if reusit:
            raspuns = QMessageBox.question(
                self,
                "Actualizare instalată",
                "Actualizarea a fost instalată cu succes.\n\n"
                "Vrei să repornești programul acum pentru a încărca noua versiune?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if raspuns == QMessageBox.StandardButton.Yes:
                self._reporneste_programul()

    def _reporneste_programul(self) -> None:
        import sys
        from PySide6.QtCore import QProcess

        try:
            QProcess.startDetached(sys.executable, sys.argv)
            if self.aplicatie is not None and hasattr(self.aplicatie, "close"):
                self.aplicatie.close()
        except Exception:
            pass

    def _revino_actualizare(self) -> None:
        """„Revino la versiunea anterioară”: restaurează o componentă din backup."""
        backup = cai.director_instalare() / actualizare.FOLDER_BACKUP
        variante = (
            sorted(p.name for p in backup.glob("*-*") if p.is_dir()) if backup.exists() else []
        )
        if not variante:
            anunta(
                self,
                "Nimic de refăcut",
                "Nu există nicio versiune veche păstrată.\n\n"
                "Copiile apar singure după o actualizare făcută din acest ecran.",
            )
            return
        alegere, ok = QInputDialog.getItem(
            self,
            "Revino la versiunea anterioară",
            "Componenta și versiunea la care revii:",
            variante,
            0,
            False,
        )
        if not ok or "-" not in alegere:
            return
        nume, versiune = alegere.rsplit("-", 1)
        if actualizare.revine(nume, versiune):
            self.et_detalii.setText(f"✔ {nume} a revenit la versiunea {versiune}.")
            seteaza_rol(self.et_detalii, "verde")
            self._verifica()
        else:
            self.et_detalii.setText(f"✘ Nu am putut readuce {nume} la versiunea {versiune}.")
            seteaza_rol(self.et_detalii, "pericol")