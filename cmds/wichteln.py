import configparser as cp
import json
from os import makedirs, path
from random import shuffle
from time import strftime

import interactions as dc


class WichtelCommand(dc.Extension):
    def __init__(self, client) -> None:
        self.client = client
        self.data_folder_path = 'data/wichteln/'
        self.data_file_path = self.data_folder_path + 'wichteln.json'
        self.wichtel_text_file_path = self.data_folder_path + 'wichteln.txt'
        self.refresh_config()
        self.load_data()

    def refresh_config(self):
        with open('config.ini', 'r') as config_file:
            config = cp.ConfigParser()
            config.read_file(config_file)
            self.wichtel_role_id = config.getint('IDs', 'wichtel_role')
            global scope_ids
            scope_ids = config.get('IDs', 'server').split(',')

    def save_data(self):
        with open(self.data_file_path, 'w+') as data_file:
            json.dump(self.data, data_file, indent=4)

    def load_data(self):
        try:
            with open(self.data_file_path, 'r') as data_file:
                self.data = json.load(data_file)
        except json.decoder.JSONDecodeError:
            self.setup_data_folder()
        except FileNotFoundError:
            self.setup_data_folder()

    def setup_data_folder(self):
        if not path.exists(self.data_folder_path):
            makedirs(self.data_folder_path)
        if not path.exists(self.data_file_path):
            open(self.data_file_path, 'a').close()
        if not path.exists(self.wichtel_text_file_path):
            open(self.wichtel_text_file_path, 'a').close()
        self.data = {
            "active": False,
            "participants": []
        }
        self.save_data()

    @dc.extension_command(
        name="wichteln",
        description="Der Befehl für das Wichteln.",
        scope=scope_ids,
        options=[
            dc.Option(
                name="aktion",
                description="Das, was du tuen willst.",
                type=dc.OptionType.STRING,
                required=True,
                choices=[
                    dc.Choice(
                        name="starten",
                        value="start"
                    ),
                    dc.Choice(
                        name="beenden",
                        value="end"
                    ),
                    dc.Choice(
                        name="bearbeiten",
                        value="edit"
                    )
                ]
            ),
            dc.Option(
                name="kanal",
                description="Der Kanal, in dem die Wichtelung stattfinden soll.",
                type=dc.OptionType.CHANNEL,
                required=False
            ),
        ]
    )
    async def wichteln(self, ctx: dc.CommandContext, aktion: str, kanal: dc.Channel = None):
        if aktion == "start":
            if not kanal:
                await ctx.send("Du musst einen Kanal angeben!", ephemeral=True)
                return
            if self.data["active"]:
                await ctx.send("Es gibt bereits eine Wichtelung.", ephemeral=True)
                return
            await ctx.defer(ephemeral=True)
            self.data["participants"] = []
            text = ""
            with open(self.wichtel_text_file_path, "r") as f:
                text = f.read()
            text.replace("$year$", strftime("%Y"))
            wichteln_embed = dc.Embed(
                title="Wichteln",
                description=text
            )
            guild: dc.Guild = await ctx.get_guild()
            minecrafter_role: dc.Role = await guild.get_role(self.wichtel_role_id)
            await kanal.send(content=minecrafter_role.mention, embeds=wichteln_embed)
            participants: list[dc.Member] = []
            guild_members = await guild.get_all_members()
            for member in guild_members:
                if self.wichtel_role_id in member.roles:
                    participants.append(member)
            shuffle(participants)
            participants.append(participants[0])
            i = 0
            for participant in participants:
                if i == len(participants) - 1:
                    break
                self.data["participants"].append(int(participant.id))
                partner = participants[i + 1].user.username
                await participant.send(f"Du bist Wichtel von {partner}!\nFür mehr Infos schaue bitte auf {guild.name}.")
                i += 1
            self.data["active"] = True
            self.save_data()
            await ctx.send("Die Wichtelung wurde erstellt.", ephemeral=True)
        elif aktion == "end":
            if not self.data["active"]:
                await ctx.send("Es gibt keine aktive Wichtelung.", ephemeral=True)
                return
            await ctx.defer(ephemeral=True)
            guild: dc.Guild = await ctx.get_guild()
            guild_id = int(guild.id)
            participants = await dc.get(self.client, list[dc.Member], parent_id=guild_id, object_ids=self.data["participants"])
            for participant in participants:
                await participant.send(f"Die Wichtelung von {guild.name} wurde beendet.")
            self.data["active"] = False
            self.save_data()
            await ctx.send("Die Wichtelung wurde beendet.", ephemeral=True)
        elif aktion == "edit":
            with open(self.wichtel_text_file_path, "r") as f:
                text = f.read()
            wichteln_text_modal = dc.Modal(
                title="Wichteltext bearbeiten",
                description="Hier kannst du den Text für die Wichtelung bearbeiten.",
                custom_id="wichteln_text",
                components=[
                    dc.TextInput(
                        label="Text",
                        placeholder="Text",
                        value=text,
                        custom_id="text",
                        style=dc.TextStyleType.PARAGRAPH,
                        required=True
                    )
                ]
            )
            await ctx.popup(wichteln_text_modal)

    @dc.extension_modal("wichteln_text")
    async def wichteln_text_response(self, ctx: dc.CommandContext, text: str):
        with open(self.wichtel_text_file_path, "w") as f:
            f.write(text)
        text = text.replace("$year$", strftime("%Y"))
        wichteln_text_preview_embed = dc.Embed(
            title="Textvorschau",
            description=text
        )
        await ctx.send("Der Text wurde gespeichert.", ephemeral=True, embeds=wichteln_text_preview_embed)


def setup(client):
    WichtelCommand(client)
