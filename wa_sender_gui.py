import csv
import time
import tkinter as tk
from tkinter import messagebox, filedialog
import os
import pyperclip

from PIL import Image
from io import BytesIO
import win32clipboard

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


CSV_FILE = "kontak.csv"

DELAY_ANTAR_PESAN = 8
WAIT_CHAT_LOAD = 60


def rapikan_nomor(nomor):
    nomor = nomor.strip()
    nomor = nomor.replace(" ", "")
    nomor = nomor.replace("-", "")
    nomor = nomor.replace("+", "")

    if nomor.startswith("0"):
        nomor = "62" + nomor[1:]

    return nomor


def baca_kontak():
    kontak = []

    with open(CSV_FILE, mode="r", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            nama = row["nama"].strip()
            nomor = rapikan_nomor(row["nomor"])
            kirim = row["kirim"].strip().lower()

            if kirim == "yes":
                kontak.append({
                    "nama": nama,
                    "nomor": nomor
                })

    return kontak


def buka_browser_whatsapp():
    try:
        options = Options()

        profile_path = os.path.abspath("wa_profile_edge")
        os.makedirs(profile_path, exist_ok=True)

        options.add_argument(f"--user-data-dir={profile_path}")
        options.add_argument("--profile-directory=Default")

        driver = webdriver.Edge(options=options)
        driver.maximize_window()

        driver.get("https://web.whatsapp.com")

        messagebox.showinfo(
            "Login WhatsApp",
            "Jika belum login, scan QR WhatsApp Web dulu.\n\n"
            "Setelah WhatsApp Web terbuka normal, klik OK."
        )

        return driver

    except Exception as e:
        messagebox.showerror(
            "Gagal membuka Edge",
            f"Edge gagal dibuka.\n\nError:\n{e}"
        )
        print("ERROR BUKA EDGE:", e)
        return None


def paste_teks_ke_box(box, teks):
    pyperclip.copy(teks)
    box.click()
    time.sleep(0.5)
    box.send_keys(Keys.CONTROL, "v")


def klik_tombol_send(driver, wait):
    tombol_send = wait.until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                "//span[@data-icon='send']/ancestor::button | "
                "//button[@aria-label='Send'] | "
                "//button[@aria-label='Kirim']"
            )
        )
    )
    tombol_send.click()


def kirim_teks(driver, wait, pesan):
    if pesan.strip() == "":
        return

    kotak_chat = wait.until(
        EC.presence_of_element_located(
            (By.XPATH, "(//footer//div[@contenteditable='true'])[last()]")
        )
    )

    time.sleep(2)

    paste_teks_ke_box(kotak_chat, pesan)

    time.sleep(1)

    try:
        klik_tombol_send(driver, wait)
    except Exception:
        kotak_chat.send_keys(Keys.ENTER)

    time.sleep(3)

def copy_image_to_clipboard(image_path):
    image = Image.open(image_path)

    if image.mode != "RGB":
        background = Image.new("RGB", image.size, "white")
        if image.mode == "RGBA":
            background.paste(image, mask=image.split()[3])
        else:
            background.paste(image)
        image = background

    output = BytesIO()
    image.save(output, "BMP")

    data = output.getvalue()[14:]
    output.close()

    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
    win32clipboard.CloseClipboard()

def kirim_foto_saja(driver, wait, image_path):
    image_full_path = os.path.abspath(image_path)

    if not os.path.exists(image_full_path):
        raise FileNotFoundError(f"File foto tidak ditemukan: {image_full_path}")

    ekstensi = os.path.splitext(image_full_path)[1].lower()

    if ekstensi == ".webp":
        raise Exception("File .webp sering terbaca sebagai sticker. Gunakan .jpg, .jpeg, atau .png.")

    print("Menyalin foto ke clipboard...")
    copy_image_to_clipboard(image_full_path)

    print("Mencari kotak chat...")

    kotak_chat = wait.until(
        EC.presence_of_element_located(
            (By.XPATH, "(//footer//div[@contenteditable='true'])[last()]")
        )
    )

    kotak_chat.click()
    time.sleep(1)

    print("Paste foto ke chat...")
    ActionChains(driver).key_down(Keys.CONTROL).send_keys("v").key_up(Keys.CONTROL).perform()

    time.sleep(8)

    print("Mencoba mencari tombol kirim foto...")

    # Cari semua kandidat tombol send yang terlihat
    kandidat_xpath = [
        "//*[contains(@data-icon,'send')]/ancestor::button[1]",
        "//*[contains(@data-icon,'send')]/ancestor::*[@role='button'][1]",
        "//button[contains(@aria-label,'Send')]",
        "//button[contains(@aria-label,'Kirim')]",
        "//*[@role='button' and contains(@aria-label,'Send')]",
        "//*[@role='button' and contains(@aria-label,'Kirim')]"
    ]

    berhasil_klik = False

    for xpath in kandidat_xpath:
        try:
            tombol_list = driver.find_elements(By.XPATH, xpath)

            print(f"XPath dicek: {xpath} | jumlah: {len(tombol_list)}")

            for tombol in reversed(tombol_list):
                try:
                    if tombol.is_displayed() and tombol.is_enabled():
                        driver.execute_script(
                            "arguments[0].scrollIntoView({block: 'center'});",
                            tombol
                        )
                        time.sleep(1)

                        try:
                            tombol.click()
                        except Exception:
                            driver.execute_script("arguments[0].click();", tombol)

                        print("Tombol kirim foto berhasil diklik.")
                        berhasil_klik = True
                        time.sleep(6)
                        break

                except Exception:
                    continue

            if berhasil_klik:
                break

        except Exception as e:
            print("Gagal cek XPath:", xpath, e)

    # Fallback 1: tekan Enter beberapa kali
    if not berhasil_klik:
        print("Tombol belum ketemu. Mencoba ENTER beberapa kali...")
        for _ in range(3):
            pyautogui.press("enter")
            time.sleep(2)

        berhasil_klik = True

    time.sleep(5)

    print("Proses kirim foto selesai.")

def kirim_pesan(driver, nomor, pesan, kirim_foto, image_path):
    url = f"https://web.whatsapp.com/send?phone={nomor}"
    driver.get(url)

    wait = WebDriverWait(driver, WAIT_CHAT_LOAD)

    print(f"Membuka chat: {nomor}")

    wait.until(
        EC.presence_of_element_located(
            (By.XPATH, "(//footer//div[@contenteditable='true'])[last()]")
        )
    )

    time.sleep(5)

    print("Chat terbuka.")

    if pesan.strip() != "":
        print("Mengirim teks...")
        kirim_teks(driver, wait, pesan)
        print("Teks terkirim.")

    if kirim_foto:
        print("Mengirim foto...")
        kirim_foto_saja(driver, wait, image_path)
        print("Foto terkirim.")

    time.sleep(DELAY_ANTAR_PESAN)


def pilih_foto():
    file_path = filedialog.askopenfilename(
        title="Pilih Foto",
        initialdir=os.getcwd(),
        filetypes=[
            ("Image Files", "*.jpg *.jpeg *.png *.webp"),
            ("All Files", "*.*")
        ]
    )

    if file_path:
        entry_foto.delete(0, tk.END)
        entry_foto.insert(0, file_path)


def kirim_semua():
    pesan_asli = kotak_pesan.get("1.0", tk.END).strip()
    image_path = entry_foto.get().strip()

    ada_marker_foto = "☑" in pesan_asli or "[foto]" in pesan_asli.lower()

    kirim_foto = kirim_foto_var.get() or ada_marker_foto

    pesan_template = pesan_asli.replace("☑", "")
    pesan_template = pesan_template.replace("[foto]", "")
    pesan_template = pesan_template.replace("[FOTO]", "")
    pesan_template = pesan_template.strip()

    if pesan_template == "" and not kirim_foto:
        messagebox.showwarning(
            "Peringatan",
            "Pesan belum diisi dan foto tidak dipilih."
        )
        return

    if kirim_foto:
        if image_path == "":
            messagebox.showwarning(
                "Peringatan",
                "Mode kirim foto aktif, tapi file foto belum dipilih."
            )
            return

        if not os.path.exists(image_path):
            messagebox.showwarning(
                "Peringatan",
                f"File foto tidak ditemukan:\n{image_path}"
            )
            return

    kontak = baca_kontak()

    if len(kontak) == 0:
        messagebox.showwarning(
            "Peringatan",
            "Tidak ada kontak dengan kirim = yes."
        )
        return

    mode_kirim = "pesan + foto" if kirim_foto else "pesan teks saja"

    konfirmasi = messagebox.askyesno(
        "Konfirmasi",
        f"Mode kirim: {mode_kirim}\n"
        f"Jumlah kontak: {len(kontak)} nomor\n\n"
        "Lanjutkan?"
    )

    if not konfirmasi:
        return

    driver = buka_browser_whatsapp()

    if driver is None:
        status_label.config(text="Gagal membuka Edge.")
        root.update()
        return

    berhasil = 0
    gagal = 0

    for orang in kontak:
        nama = orang["nama"]
        nomor = orang["nomor"]

        pesan_personal = pesan_template

        pesan_personal = pesan_personal.replace("[nama]", nama)
        pesan_personal = pesan_personal.replace("[Nama]", nama)
        pesan_personal = pesan_personal.replace("[NAMA]", nama)
        pesan_personal = pesan_personal.replace("[ nama ]", nama)

        pesan_personal = pesan_personal.replace("[nomor]", nomor)
        pesan_personal = pesan_personal.replace("[Nomor]", nomor)
        pesan_personal = pesan_personal.replace("[NOMOR]", nomor)

        print("PESAN FINAL:", pesan_personal)

        status_label.config(text=f"Mengirim ke {nama} - {nomor}")
        root.update()

        try:
            kirim_pesan(driver, nomor, pesan_personal, kirim_foto, image_path)

            berhasil += 1
            status_label.config(text=f"Berhasil kirim ke {nama}")
            root.update()

        except Exception as e:
            gagal += 1
            print(f"Gagal kirim ke {nama} - {nomor}: {e}")
            status_label.config(text=f"Gagal kirim ke {nama}")
            root.update()
            time.sleep(3)

    status_label.config(text=f"Selesai. Berhasil: {berhasil}, Gagal: {gagal}")
    messagebox.showinfo(
        "Selesai",
        f"Proses selesai.\n\nBerhasil: {berhasil}\nGagal: {gagal}"
    )


root = tk.Tk()
root.title("WhatsApp Auto Sender")
root.geometry("640x560")

judul = tk.Label(
    root,
    text="WhatsApp Auto Sender",
    font=("Arial", 16, "bold")
)
judul.pack(pady=10)

label_pesan = tk.Label(
    root,
    text="Masukkan pesan. Gunakan [nama]. Tambahkan ☑ atau [foto] jika ingin kirim foto:"
)
label_pesan.pack()

kotak_pesan = tk.Text(root, height=10, width=72)
kotak_pesan.pack(pady=10)

kirim_foto_var = tk.BooleanVar(value=False)

checkbox_foto = tk.Checkbutton(
    root,
    text="Kirim foto juga",
    variable=kirim_foto_var,
    font=("Arial", 10)
)
checkbox_foto.pack(pady=5)

frame_foto = tk.Frame(root)
frame_foto.pack(pady=5)

entry_foto = tk.Entry(frame_foto, width=58)
entry_foto.pack(side=tk.LEFT, padx=5)

entry_foto.insert(0, "poster.jpg")

tombol_pilih_foto = tk.Button(
    frame_foto,
    text="Pilih Foto",
    command=pilih_foto
)
tombol_pilih_foto.pack(side=tk.LEFT)

tombol_kirim = tk.Button(
    root,
    text="KIRIM SEMUA",
    font=("Arial", 12, "bold"),
    bg="green",
    fg="white",
    command=kirim_semua
)
tombol_kirim.pack(pady=15)

status_label = tk.Label(
    root,
    text="Menunggu perintah...",
    fg="blue"
)
status_label.pack(pady=10)

catatan = tk.Label(
    root,
    text="Foto bisa dipilih lewat tombol Pilih Foto. Pesan bisa personal dengan [nama].",
    fg="gray"
)
catatan.pack(pady=5)

root.mainloop()