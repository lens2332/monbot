import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from datetime import datetime

# ─────────────────────────────────────────
#  CONFIG & DATA
# ─────────────────────────────────────────

DATA_FILE = "data.json"
CONFIG_FILE = "config.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "shop": [], "quests": []}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {"token": "TON_TOKEN_ICI", "admin_ids": [], "currency_name": "💰 Pièces"}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

config = load_config()

# ─────────────────────────────────────────
#  BOT SETUP
# ─────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def is_admin(user_id: int):
    return user_id in config.get("admin_ids", [])

def get_balance(user_id: str, data: dict) -> int:
    return data["users"].get(user_id, {}).get("balance", 0)

def set_balance(user_id: str, amount: int, data: dict):
    if user_id not in data["users"]:
        data["users"][user_id] = {"balance": 0, "purchased": [], "completed_quests": []}
    data["users"][user_id]["balance"] = amount

currency = config.get("currency_name", "💰 Pièces")

# ─────────────────────────────────────────
#  VIEWS — BOUTIQUE
# ─────────────────────────────────────────

class ShopView(discord.ui.View):
    def __init__(self, items: list, user_id: int):
        super().__init__(timeout=120)
        self.items = items
        self.user_id = user_id
        self.page = 0
        self.items_per_page = 5
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        start = self.page * self.items_per_page
        end = start + self.items_per_page
        page_items = self.items[start:end]

        for i, item in enumerate(page_items):
            btn = discord.ui.Button(
                label=f"{item['emoji']} {item['name']} — {item['price']} pièces",
                style=discord.ButtonStyle.primary,
                custom_id=f"buy_{start+i}",
                row=i
            )
            btn.callback = self.make_buy_callback(start + i)
            self.add_item(btn)

        # Navigation
        nav_row = 4
        if self.page > 0:
            prev_btn = discord.ui.Button(label="◀ Précédent", style=discord.ButtonStyle.secondary, row=nav_row)
            prev_btn.callback = self.prev_page
            self.add_item(prev_btn)
        if end < len(self.items):
            next_btn = discord.ui.Button(label="Suivant ▶", style=discord.ButtonStyle.secondary, row=nav_row)
            next_btn.callback = self.next_page
            self.add_item(next_btn)

    def make_buy_callback(self, index):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("❌ Ce menu n'est pas pour toi !", ephemeral=True)
                return
            data = load_data()
            uid = str(interaction.user.id)
            item = self.items[index]
            bal = get_balance(uid, data)
            purchased = data["users"].get(uid, {}).get("purchased", [])

            if item["name"] in purchased:
                await interaction.response.send_message(f"⚠️ Tu possèdes déjà **{item['name']}** !", ephemeral=True)
                return
            if bal < item["price"]:
                await interaction.response.send_message(
                    f"❌ Pas assez de pièces ! Tu as **{bal}** pièces, il en faut **{item['price']}**.", ephemeral=True
                )
                return

            set_balance(uid, bal - item["price"], data)
            if uid not in data["users"]:
                data["users"][uid] = {"balance": 0, "purchased": [], "completed_quests": []}
            data["users"][uid]["purchased"].append(item["name"])
            save_data(data)

            embed = discord.Embed(
                title="✅ Achat réussi !",
                description=f"Tu as acheté **{item['emoji']} {item['name']}** pour **{item['price']} pièces** !\nSolde restant : **{bal - item['price']} pièces**",
                color=0x57F287
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        return callback

    async def prev_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Ce menu n'est pas pour toi !", ephemeral=True)
            return
        self.page -= 1
        self.update_buttons()
        await interaction.response.edit_message(view=self)

    async def next_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Ce menu n'est pas pour toi !", ephemeral=True)
            return
        self.page += 1
        self.update_buttons()
        await interaction.response.edit_message(view=self)


# ─────────────────────────────────────────
#  VIEWS — QUÊTES
# ─────────────────────────────────────────

class QuestView(discord.ui.View):
    def __init__(self, quests: list, user_id: int):
        super().__init__(timeout=120)
        self.quests = quests
        self.user_id = user_id
        self.page = 0
        self.quests_per_page = 4
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        start = self.page * self.quests_per_page
        end = start + self.quests_per_page
        page_quests = self.quests[start:end]

        for i, quest in enumerate(page_quests):
            btn = discord.ui.Button(
                label=f"📜 {quest['name']} (+{quest['reward']} pièces)",
                style=discord.ButtonStyle.success,
                custom_id=f"quest_{start+i}",
                row=i
            )
            btn.callback = self.make_quest_callback(start + i)
            self.add_item(btn)

        nav_row = 4
        if self.page > 0:
            prev_btn = discord.ui.Button(label="◀ Précédent", style=discord.ButtonStyle.secondary, row=nav_row)
            prev_btn.callback = self.prev_page
            self.add_item(prev_btn)
        if end < len(self.quests):
            next_btn = discord.ui.Button(label="Suivant ▶", style=discord.ButtonStyle.secondary, row=nav_row)
            next_btn.callback = self.next_page
            self.add_item(next_btn)

    def make_quest_callback(self, index):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("❌ Ce menu n'est pas pour toi !", ephemeral=True)
                return
            data = load_data()
            uid = str(interaction.user.id)
            quest = self.quests[index]
            completed = data["users"].get(uid, {}).get("completed_quests", [])

            if quest["name"] in completed:
                await interaction.response.send_message(f"✅ Tu as déjà complété la quête **{quest['name']}** !", ephemeral=True)
                return

            # Show quest detail
            embed = discord.Embed(
                title=f"📜 {quest['name']}",
                description=quest["description"],
                color=0xFEE75C
            )
            embed.add_field(name="🏆 Récompense", value=f"{quest['reward']} pièces", inline=True)
            embed.add_field(name="📊 Difficulté", value=quest.get("difficulty", "Normale"), inline=True)
            embed.set_footer(text="Clique sur Valider quand tu as terminé !")

            claim_view = QuestClaimView(quest, uid, interaction.user.id)
            await interaction.response.send_message(embed=embed, view=claim_view, ephemeral=True)
        return callback

    async def prev_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Ce menu n'est pas pour toi !", ephemeral=True)
            return
        self.page -= 1
        self.update_buttons()
        await interaction.response.edit_message(view=self)

    async def next_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Ce menu n'est pas pour toi !", ephemeral=True)
            return
        self.page += 1
        self.update_buttons()
        await interaction.response.edit_message(view=self)


class QuestClaimView(discord.ui.View):
    def __init__(self, quest: dict, uid: str, user_id: int):
        super().__init__(timeout=60)
        self.quest = quest
        self.uid = uid
        self.user_id = user_id

    @discord.ui.button(label="✅ Valider la quête", style=discord.ButtonStyle.success)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Ce menu n'est pas pour toi !", ephemeral=True)
            return
        data = load_data()
        completed = data["users"].get(self.uid, {}).get("completed_quests", [])
        if self.quest["name"] in completed:
            await interaction.response.send_message("⚠️ Quête déjà réclamée !", ephemeral=True)
            return

        bal = get_balance(self.uid, data)
        set_balance(self.uid, bal + self.quest["reward"], data)
        if self.uid not in data["users"]:
            data["users"][self.uid] = {"balance": 0, "purchased": [], "completed_quests": []}
        data["users"][self.uid]["completed_quests"].append(self.quest["name"])
        save_data(data)

        embed = discord.Embed(
            title="🎉 Quête complétée !",
            description=f"**{self.quest['name']}** terminée !\nTu as gagné **{self.quest['reward']} pièces** !\nNouveau solde : **{bal + self.quest['reward']} pièces**",
            color=0x57F287
        )
        await interaction.response.edit_message(embed=embed, view=None)


# ─────────────────────────────────────────
#  SLASH COMMANDS — PUBLIC
# ─────────────────────────────────────────

@bot.tree.command(name="boutique", description="Ouvre la boutique interactive 🛍️")
async def boutique(interaction: discord.Interaction):
    data = load_data()
    items = data.get("shop", [])

    if not items:
        await interaction.response.send_message("🛒 La boutique est vide pour l'instant !", ephemeral=True)
        return

    uid = str(interaction.user.id)
    bal = get_balance(uid, data)
    purchased = data["users"].get(uid, {}).get("purchased", [])

    embed = discord.Embed(
        title="🛍️ Boutique",
        description=f"Solde actuel : **{bal} pièces** | Articles achetés : **{len(purchased)}**\n\nClique sur un article pour l'acheter !",
        color=0x5865F2
    )
    for item in items[:5]:
        status = "✅ Acheté" if item["name"] in purchased else f"{item['price']} pièces"
        embed.add_field(
            name=f"{item['emoji']} {item['name']}",
            value=f"{item['description']}\n**Prix :** {status}",
            inline=True
        )

    view = ShopView(items, interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@bot.tree.command(name="solde", description="Voir ton solde de pièces 💰")
async def solde(interaction: discord.Interaction):
    data = load_data()
    uid = str(interaction.user.id)
    bal = get_balance(uid, data)
    purchased = data["users"].get(uid, {}).get("purchased", [])
    completed = data["users"].get(uid, {}).get("completed_quests", [])

    embed = discord.Embed(
        title=f"💰 Solde de {interaction.user.display_name}",
        color=0xFEE75C
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.add_field(name="💵 Pièces", value=f"**{bal}**", inline=True)
    embed.add_field(name="🛍️ Achats", value=f"**{len(purchased)}** articles", inline=True)
    embed.add_field(name="📜 Quêtes", value=f"**{len(completed)}** complétées", inline=True)
    embed.set_footer(text=f"Consulté le {datetime.now().strftime('%d/%m/%Y à %H:%M')}")

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="quete", description="Voir et compléter les quêtes disponibles 📜")
async def quete(interaction: discord.Interaction):
    data = load_data()
    quests = data.get("quests", [])

    if not quests:
        await interaction.response.send_message("📜 Aucune quête disponible pour l'instant !", ephemeral=True)
        return

    uid = str(interaction.user.id)
    completed = data["users"].get(uid, {}).get("completed_quests", [])

    embed = discord.Embed(
        title="📜 Quêtes disponibles",
        description=f"Quêtes complétées : **{len(completed)}/{len(quests)}**\n\nClique sur une quête pour voir les détails !",
        color=0xEB459E
    )
    for quest in quests[:4]:
        status = "✅ Complétée" if quest["name"] in completed else f"+{quest['reward']} pièces"
        embed.add_field(
            name=f"📜 {quest['name']}",
            value=f"{quest['description'][:80]}...\n**Récompense :** {status}",
            inline=False
        )

    view = QuestView(quests, interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ─────────────────────────────────────────
#  SLASH COMMANDS — ADMIN
# ─────────────────────────────────────────

@bot.tree.command(name="admin", description="[ADMIN] Panneau de commandes admin 🔧")
async def admin(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Tu n'as pas la permission d'utiliser cette commande !", ephemeral=True)
        return

    embed = discord.Embed(
        title="🔧 Panneau Admin",
        description="Toutes les commandes disponibles pour gérer le bot :",
        color=0xED4245
    )
    embed.add_field(
        name="💰 Économie",
        value="`/donner_argent @user montant` — Donner des pièces\n`/retirer_argent @user montant` — Retirer des pièces\n`/reset_solde @user` — Remettre le solde à 0",
        inline=False
    )
    embed.add_field(
        name="🛍️ Boutique",
        value="`/ajouter_item nom prix emoji description` — Ajouter un article\n`/supprimer_item nom` — Supprimer un article\n`/voir_boutique` — Voir tous les articles",
        inline=False
    )
    embed.add_field(
        name="📜 Quêtes",
        value="`/ajouter_quete nom description recompense difficulte` — Ajouter une quête\n`/supprimer_quete nom` — Supprimer une quête\n`/voir_quetes` — Voir toutes les quêtes",
        inline=False
    )
    embed.add_field(
        name="👥 Joueurs",
        value="`/voir_joueur @user` — Voir le profil d'un joueur\n`/top` — Classement des plus riches",
        inline=False
    )
    embed.set_footer(text="⚠️ Commandes réservées aux admins")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="donner_argent", description="[ADMIN] Donner des pièces à un joueur")
@app_commands.describe(membre="Le membre à créditer", montant="Montant à donner")
async def donner_argent(interaction: discord.Interaction, membre: discord.Member, montant: int):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Permission refusée !", ephemeral=True)
        return
    if montant <= 0:
        await interaction.response.send_message("❌ Le montant doit être positif !", ephemeral=True)
        return

    data = load_data()
    uid = str(membre.id)
    bal = get_balance(uid, data)
    set_balance(uid, bal + montant, data)
    save_data(data)

    embed = discord.Embed(
        title="💰 Pièces données",
        description=f"**{montant} pièces** données à {membre.mention}\nNouveau solde : **{bal + montant} pièces**",
        color=0x57F287
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="retirer_argent", description="[ADMIN] Retirer des pièces à un joueur")
@app_commands.describe(membre="Le membre à débiter", montant="Montant à retirer")
async def retirer_argent(interaction: discord.Interaction, membre: discord.Member, montant: int):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Permission refusée !", ephemeral=True)
        return

    data = load_data()
    uid = str(membre.id)
    bal = get_balance(uid, data)
    new_bal = max(0, bal - montant)
    set_balance(uid, new_bal, data)
    save_data(data)

    embed = discord.Embed(
        title="💸 Pièces retirées",
        description=f"**{montant} pièces** retirées à {membre.mention}\nNouveau solde : **{new_bal} pièces**",
        color=0xED4245
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="reset_solde", description="[ADMIN] Remettre le solde d'un joueur à 0")
@app_commands.describe(membre="Le membre à réinitialiser")
async def reset_solde(interaction: discord.Interaction, membre: discord.Member):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Permission refusée !", ephemeral=True)
        return

    data = load_data()
    uid = str(membre.id)
    set_balance(uid, 0, data)
    save_data(data)
    await interaction.response.send_message(f"🔄 Solde de {membre.mention} remis à **0 pièces**.")


@bot.tree.command(name="ajouter_item", description="[ADMIN] Ajouter un article à la boutique")
@app_commands.describe(nom="Nom de l'article", prix="Prix en pièces", emoji="Emoji de l'article", description="Description")
async def ajouter_item(interaction: discord.Interaction, nom: str, prix: int, emoji: str, description: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Permission refusée !", ephemeral=True)
        return

    data = load_data()
    # Check duplicate
    for item in data["shop"]:
        if item["name"].lower() == nom.lower():
            await interaction.response.send_message(f"⚠️ Un article nommé **{nom}** existe déjà !", ephemeral=True)
            return

    data["shop"].append({"name": nom, "price": prix, "emoji": emoji, "description": description})
    save_data(data)

    embed = discord.Embed(
        title="✅ Article ajouté",
        description=f"**{emoji} {nom}** ajouté à la boutique pour **{prix} pièces** !",
        color=0x57F287
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="supprimer_item", description="[ADMIN] Supprimer un article de la boutique")
@app_commands.describe(nom="Nom de l'article à supprimer")
async def supprimer_item(interaction: discord.Interaction, nom: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Permission refusée !", ephemeral=True)
        return

    data = load_data()
    before = len(data["shop"])
    data["shop"] = [i for i in data["shop"] if i["name"].lower() != nom.lower()]

    if len(data["shop"]) == before:
        await interaction.response.send_message(f"❌ Article **{nom}** introuvable !", ephemeral=True)
        return

    save_data(data)
    await interaction.response.send_message(f"🗑️ Article **{nom}** supprimé de la boutique !")


@bot.tree.command(name="voir_boutique", description="[ADMIN] Voir tous les articles de la boutique")
async def voir_boutique(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Permission refusée !", ephemeral=True)
        return

    data = load_data()
    items = data.get("shop", [])

    if not items:
        await interaction.response.send_message("🛒 La boutique est vide !", ephemeral=True)
        return

    embed = discord.Embed(title="🛍️ Articles en boutique", color=0x5865F2)
    for item in items:
        embed.add_field(
            name=f"{item['emoji']} {item['name']}",
            value=f"Prix : **{item['price']}** pièces\n{item['description']}",
            inline=True
        )
    embed.set_footer(text=f"{len(items)} article(s) au total")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="ajouter_quete", description="[ADMIN] Ajouter une quête")
@app_commands.describe(nom="Nom de la quête", description="Description", recompense="Récompense en pièces", difficulte="Difficulté (Facile/Normale/Difficile)")
async def ajouter_quete(interaction: discord.Interaction, nom: str, description: str, recompense: int, difficulte: str = "Normale"):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Permission refusée !", ephemeral=True)
        return

    data = load_data()
    for q in data["quests"]:
        if q["name"].lower() == nom.lower():
            await interaction.response.send_message(f"⚠️ Une quête nommée **{nom}** existe déjà !", ephemeral=True)
            return

    data["quests"].append({"name": nom, "description": description, "reward": recompense, "difficulty": difficulte})
    save_data(data)

    embed = discord.Embed(
        title="✅ Quête ajoutée",
        description=f"**📜 {nom}** ajoutée avec une récompense de **{recompense} pièces** !",
        color=0x57F287
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="supprimer_quete", description="[ADMIN] Supprimer une quête")
@app_commands.describe(nom="Nom de la quête à supprimer")
async def supprimer_quete(interaction: discord.Interaction, nom: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Permission refusée !", ephemeral=True)
        return

    data = load_data()
    before = len(data["quests"])
    data["quests"] = [q for q in data["quests"] if q["name"].lower() != nom.lower()]

    if len(data["quests"]) == before:
        await interaction.response.send_message(f"❌ Quête **{nom}** introuvable !", ephemeral=True)
        return

    save_data(data)
    await interaction.response.send_message(f"🗑️ Quête **{nom}** supprimée !")


@bot.tree.command(name="voir_quetes", description="[ADMIN] Voir toutes les quêtes")
async def voir_quetes(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Permission refusée !", ephemeral=True)
        return

    data = load_data()
    quests = data.get("quests", [])

    if not quests:
        await interaction.response.send_message("📜 Aucune quête !", ephemeral=True)
        return

    embed = discord.Embed(title="📜 Liste des quêtes", color=0xEB459E)
    for quest in quests:
        embed.add_field(
            name=f"📜 {quest['name']} [{quest.get('difficulty', 'Normale')}]",
            value=f"{quest['description']}\n**Récompense :** {quest['reward']} pièces",
            inline=False
        )
    embed.set_footer(text=f"{len(quests)} quête(s) au total")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="voir_joueur", description="[ADMIN] Voir le profil complet d'un joueur")
@app_commands.describe(membre="Le membre à inspecter")
async def voir_joueur(interaction: discord.Interaction, membre: discord.Member):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Permission refusée !", ephemeral=True)
        return

    data = load_data()
    uid = str(membre.id)
    user_data = data["users"].get(uid, {"balance": 0, "purchased": [], "completed_quests": []})

    embed = discord.Embed(title=f"👤 Profil de {membre.display_name}", color=0x5865F2)
    embed.set_thumbnail(url=membre.display_avatar.url)
    embed.add_field(name="💰 Solde", value=f"{user_data.get('balance', 0)} pièces", inline=True)
    embed.add_field(name="🛍️ Achats", value="\n".join(user_data.get("purchased", [])) or "Aucun", inline=True)
    embed.add_field(name="📜 Quêtes complétées", value="\n".join(user_data.get("completed_quests", [])) or "Aucune", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="top", description="Voir le classement des joueurs les plus riches 🏆")
async def top(interaction: discord.Interaction):
    data = load_data()
    users = data.get("users", {})

    if not users:
        await interaction.response.send_message("Aucun joueur enregistré !", ephemeral=True)
        return

    sorted_users = sorted(users.items(), key=lambda x: x[1].get("balance", 0), reverse=True)[:10]

    embed = discord.Embed(title="🏆 Top 10 — Les plus riches", color=0xFEE75C)
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    desc = ""
    for i, (uid, udata) in enumerate(sorted_users):
        try:
            user = await bot.fetch_user(int(uid))
            name = user.display_name
        except Exception:
            name = f"Joueur#{uid[:4]}"
        desc += f"{medals[i]} **{name}** — {udata.get('balance', 0)} pièces\n"

    embed.description = desc
    await interaction.response.send_message(embed=embed)


# ─────────────────────────────────────────
#  EVENTS
# ─────────────────────────────────────────

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ {bot.user} est connecté et prêt !")
    print(f"📡 Slash commands synchronisées !")
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name="/boutique | /quete | /solde"
    ))


# ─────────────────────────────────────────
#  LAUNCH
# ─────────────────────────────────────────

if __name__ == "__main__":
    token = config.get("token", "")
    if not token or token == "TON_TOKEN_ICI":
        print("❌ Erreur : mets ton token Discord dans config.json !")
    else:
        bot.run(token)
