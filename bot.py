import os
import re

import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()


def env_requerida(nombre: str) -> str:
    valor = os.getenv(nombre)
    if valor is None or not valor.strip():
        raise RuntimeError(f"Falta la variable de entorno obligatoria: {nombre}")
    return valor.strip()


def env_entero(nombre: str) -> int:
    valor = env_requerida(nombre)
    try:
        return int(valor)
    except ValueError as error:
        raise RuntimeError(
            f"La variable {nombre} debe contener un ID numérico de Discord."
        ) from error


TOKEN = env_requerida("DISCORD_TOKEN")
GUILD_ID = env_entero("GUILD_ID")

ROL_ESTUDIANTE_ID = env_entero("ROL_ESTUDIANTE_ID")
ROL_REP_ID = env_entero("ROL_REP_ID")

CANAL_REGISTRO_LOGS_ID = env_entero("CANAL_REGISTRO_LOGS_ID")
CANAL_LOGS_ANONIMOS_ID = env_entero("CANAL_LOGS_ANONIMOS_ID")

CANAL_SUGERENCIAS_ID = env_entero("CANAL_SUGERENCIAS_ID")
CANAL_DUDAS_ANONIMAS_ID = env_entero("CANAL_DUDAS_ANONIMAS_ID")
CANAL_DENUNCIAS_ID = env_entero("CANAL_DENUNCIAS_ID")
CANAL_DENUNCIAS_REPRES_ID = env_entero("CANAL_DENUNCIAS_REPRES_ID")

GUILD = discord.Object(id=GUILD_ID)

EMAIL_EAFIT_REGEX = re.compile(
    r"^[A-Za-z0-9._%+\-]+@eafit\.edu\.co$",
    re.IGNORECASE,
)


class RegistroBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        self.add_view(BotonRegistro())
        self.add_view(BotonResponder())
        await self.tree.sync(guild=GUILD)
        print("Comandos sincronizados.")


bot = RegistroBot()


def obtener_rol(guild: discord.Guild, role_id: int):
    return guild.get_role(role_id)


def obtener_canal(guild: discord.Guild, channel_id: int):
    return guild.get_channel(channel_id)


def usuario_esta_registrado(member: discord.Member, guild: discord.Guild) -> bool:
    rol_estudiante = obtener_rol(guild, ROL_ESTUDIANTE_ID)
    return rol_estudiante is not None and rol_estudiante in member.roles


def bot_puede_gestionar_rol(guild: discord.Guild, rol: discord.Role) -> bool:
    bot_member = guild.me
    if bot_member is None:
        return False
    return (
        bot_member.guild_permissions.manage_roles
        and rol < bot_member.top_role
        and not rol.managed
    )


class RegistroModal(discord.ui.Modal, title="Registro - Ingeniería de Sistemas EAFIT"):
    nombre = discord.ui.TextInput(
        label="Nombre completo",
        placeholder="Ej: Isabella García",
        required=True,
        min_length=3,
        max_length=100,
    )

    correo = discord.ui.TextInput(
        label="Correo institucional",
        placeholder="tu.correo@eafit.edu.co",
        required=True,
        min_length=10,
        max_length=120,
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        miembro = interaction.user

        if guild is None or not isinstance(miembro, discord.Member):
            await interaction.response.send_message(
                "No pude identificar el servidor o tu usuario.",
                ephemeral=True,
            )
            return

        correo = self.correo.value.strip().lower()
        nombre = " ".join(self.nombre.value.strip().split())

        if not EMAIL_EAFIT_REGEX.fullmatch(correo):
            await interaction.response.send_message(
                "Debes usar un correo institucional válido `@eafit.edu.co`.",
                ephemeral=True,
            )
            return

        rol_estudiante = obtener_rol(guild, ROL_ESTUDIANTE_ID)

        if rol_estudiante is None:
            await interaction.response.send_message(
                "El rol de estudiante no está configurado correctamente.",
                ephemeral=True,
            )
            return

        if rol_estudiante in miembro.roles:
            await interaction.response.send_message(
                "Ya estás registrado y ya tienes el rol de estudiante.",
                ephemeral=True,
            )
            return

        if not bot_puede_gestionar_rol(guild, rol_estudiante):
            await interaction.response.send_message(
                "No puedo asignar el rol de estudiante. Revisa la jerarquía y el permiso Administrar roles.",
                ephemeral=True,
            )
            return

        try:
            await miembro.add_roles(
                rol_estudiante,
                reason="Registro de estudiante mediante el bot de registro",
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "Discord no me permitió asignar el rol de estudiante.",
                ephemeral=True,
            )
            return
        except discord.HTTPException as error:
            await interaction.response.send_message(
                f"Discord devolvió un error al registrar el usuario: {error}",
                ephemeral=True,
            )
            return

        canal_logs = obtener_canal(guild, CANAL_REGISTRO_LOGS_ID)

        if isinstance(canal_logs, discord.TextChannel):
            embed = discord.Embed(
                title="Nuevo registro",
                color=discord.Color.green(),
            )
            embed.add_field(name="Usuario", value=miembro.mention, inline=False)
            embed.add_field(name="Nombre declarado", value=nombre, inline=False)
            embed.add_field(name="Correo declarado", value=correo, inline=False)
            embed.set_footer(text=f"ID de Discord: {miembro.id}")

            try:
                await canal_logs.send(embed=embed)
            except discord.HTTPException as error:
                print(f"No pude guardar el log de registro: {error}")

        await interaction.response.send_message(
            "Registro completado. Ya tienes el rol de estudiante y puedes continuar con la selección de materias.\n\n"
            "**Importante:** este sistema valida el formato del correo `@eafit.edu.co`, "
            "pero no verifica que tengas acceso real a esa cuenta.",
            ephemeral=True,
        )


class BotonRegistro(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Registrarme",
        style=discord.ButtonStyle.primary,
        emoji="📝",
        custom_id="registro_abrir_modal",
    )
    async def registrar(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        guild = interaction.guild
        member = interaction.user

        if guild is None or not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "Este botón solo funciona dentro del servidor.",
                ephemeral=True,
            )
            return

        if usuario_esta_registrado(member, guild):
            await interaction.response.send_message(
                "Ya estás registrado y tienes el rol de estudiante.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(RegistroModal())


@bot.tree.command(
    name="iniciar_registro",
    description="Publica o actualiza el panel de registro.",
)
@app_commands.guilds(GUILD)
@app_commands.checks.has_permissions(administrator=True)
async def iniciar_registro(interaction: discord.Interaction):
    canal = interaction.channel

    if not isinstance(canal, discord.TextChannel):
        await interaction.response.send_message(
            "Este comando debe ejecutarse en un canal de texto.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)

    embed = discord.Embed(
        title="Registro - Ingeniería de Sistemas EAFIT",
        description=(
            "Para acceder al servidor debes registrarte con tu nombre completo "
            "y un correo institucional `@eafit.edu.co`.\n\n"
            "Pulsa **Registrarme** para comenzar."
        ),
        color=discord.Color.blue(),
    )

    mensaje_panel = None

    try:
        async for mensaje in canal.history(limit=50):
            if (
                bot.user is not None
                and mensaje.author.id == bot.user.id
                and mensaje.embeds
                and mensaje.embeds[0].title == "Registro - Ingeniería de Sistemas EAFIT"
            ):
                mensaje_panel = mensaje
                break
    except discord.HTTPException:
        pass

    if mensaje_panel is not None:
        await mensaje_panel.edit(embed=embed, view=BotonRegistro())
    else:
        await canal.send(embed=embed, view=BotonRegistro())

    await interaction.followup.send(
        "Panel de registro publicado correctamente.",
        ephemeral=True,
    )


CANALES_ANONIMOS = {
    CANAL_SUGERENCIAS_ID: {
        "emoji": "💡",
        "titulo": "Sugerencia anónima",
        "color": discord.Color.blue(),
    },
    CANAL_DUDAS_ANONIMAS_ID: {
        "emoji": "❓",
        "titulo": "Duda anónima",
        "color": discord.Color.yellow(),
    },
    CANAL_DENUNCIAS_ID: {
        "emoji": "🚨",
        "titulo": "Denuncia anónima",
        "color": discord.Color.red(),
    },
}


class ResponderModal(discord.ui.Modal, title="Responder duda"):
    respuesta = discord.ui.TextInput(
        label="Respuesta",
        style=discord.TextStyle.paragraph,
        placeholder="Escribe tu respuesta aquí...",
        required=True,
        min_length=1,
        max_length=1500,
    )

    def __init__(self, mensaje_original: str, canal_id: int):
        super().__init__()
        self.mensaje_original = mensaje_original
        self.canal_id = canal_id

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user

        if guild is None or not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "No pude identificar tu usuario.",
                ephemeral=True,
            )
            return

        if not usuario_esta_registrado(member, guild):
            await interaction.response.send_message(
                "Debes estar registrado como estudiante para responder.",
                ephemeral=True,
            )
            return

        canal = guild.get_channel(self.canal_id)

        if not isinstance(canal, discord.TextChannel):
            await interaction.response.send_message(
                "No pude encontrar el canal original.",
                ephemeral=True,
            )
            return

        rol_rep = obtener_rol(guild, ROL_REP_ID)
        es_rep = rol_rep is not None and rol_rep in member.roles

        titulo = "Respuesta de representantes" if es_rep else "Respuesta anónima"
        color = discord.Color.green() if es_rep else discord.Color.greyple()

        embed = discord.Embed(
            title=titulo,
            description=self.respuesta.value,
            color=color,
        )
        embed.add_field(
            name="Duda original",
            value=self.mensaje_original[:1024],
            inline=False,
        )

        try:
            await canal.send(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message(
                "No tengo permiso para publicar la respuesta en ese canal.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "Respuesta publicada.",
            ephemeral=True,
        )


class BotonResponder(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Responder",
        style=discord.ButtonStyle.green,
        emoji="💬",
        custom_id="anonimo_responder_duda",
    )
    async def responder(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        mensaje = interaction.message

        if mensaje is None or not mensaje.embeds:
            await interaction.response.send_message(
                "No pude recuperar la duda original.",
                ephemeral=True,
            )
            return

        embed = mensaje.embeds[0]
        mensaje_original = embed.description or "Duda sin contenido disponible"

        await interaction.response.send_modal(
            ResponderModal(
                mensaje_original=mensaje_original,
                canal_id=interaction.channel_id,
            )
        )


@bot.tree.command(
    name="anonimo",
    description="Publica sin mostrar tu nombre; moderación conserva un log privado.",
)
@app_commands.guilds(GUILD)
@app_commands.describe(mensaje="Mensaje que deseas publicar")
async def anonimo(interaction: discord.Interaction, mensaje: str):
    guild = interaction.guild
    member = interaction.user

    if guild is None or not isinstance(member, discord.Member):
        await interaction.response.send_message(
            "Este comando solo funciona dentro del servidor.",
            ephemeral=True,
        )
        return

    if not usuario_esta_registrado(member, guild):
        await interaction.response.send_message(
            "Debes registrarte antes de usar los canales anónimos.",
            ephemeral=True,
        )
        return

    configuracion = CANALES_ANONIMOS.get(interaction.channel_id)

    if configuracion is None:
        await interaction.response.send_message(
            "Este comando solo funciona en los canales configurados para sugerencias, dudas anónimas o denuncias.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)

    embed = discord.Embed(
        title=f"{configuracion['emoji']} {configuracion['titulo']}",
        description=mensaje,
        color=configuracion["color"],
    )
    embed.set_footer(text="Mensaje publicado sin mostrar la identidad del autor")

    try:

        # =====================================================
        # DENUNCIAS
        # Se envían únicamente al canal privado de representantes
        # =====================================================

        if interaction.channel_id == CANAL_DENUNCIAS_ID:

            canal_denuncias_repres = obtener_canal(
                guild,
                CANAL_DENUNCIAS_REPRES_ID
            )

            if not isinstance(
                    canal_denuncias_repres,
                    discord.TextChannel
            ):
                await interaction.followup.send(
                    (
                        "El canal privado de denuncias "
                        "no está configurado correctamente."
                    ),
                    ephemeral=True
                )
                return

            embed_denuncia = discord.Embed(
                title="🚨 Nueva denuncia",
                description=mensaje,
                color=discord.Color.red()
            )

            embed_denuncia.add_field(
                name="Autor",
                value=member.mention,
                inline=False
            )

            embed_denuncia.add_field(
                name="ID de usuario",
                value=str(member.id),
                inline=False
            )

            await canal_denuncias_repres.send(
                embed=embed_denuncia
            )

        # =====================================================
        # DUDAS ANÓNIMAS
        # Son públicas y permiten respuestas
        # =====================================================

        elif interaction.channel_id == CANAL_DUDAS_ANONIMAS_ID:

            await interaction.channel.send(
                embed=embed,
                view=BotonResponder()
            )

        # =====================================================
        # SUGERENCIAS
        # Son públicas pero anónimas
        # =====================================================

        else:

            await interaction.channel.send(
                embed=embed
            )

    except discord.Forbidden:

        await interaction.followup.send(
            "No tengo permiso para publicar en el canal correspondiente.",
            ephemeral=True
        )
        return


    canal_logs = obtener_canal(guild, CANAL_LOGS_ANONIMOS_ID)

    if isinstance(canal_logs, discord.TextChannel):
        embed_log = discord.Embed(
            title="Log de mensaje anónimo",
            color=discord.Color.greyple(),
        )
        embed_log.add_field(
            name="Canal",
            value=interaction.channel.mention,
            inline=True,
        )
        embed_log.add_field(
            name="Usuario",
            value=member.mention,
            inline=True,
        )
        embed_log.add_field(
            name="ID de usuario",
            value=str(member.id),
            inline=False,
        )
        embed_log.add_field(
            name="Mensaje",
            value=mensaje[:1024],
            inline=False,
        )

        try:
            await canal_logs.send(embed=embed_log)
        except discord.HTTPException as error:
            print(f"No pude guardar el log anónimo: {error}")

    if interaction.channel_id == CANAL_DENUNCIAS_ID:

        await interaction.followup.send(
            (
                "Tu denuncia fue enviada correctamente "
                "a los representantes.\n\n"
                "La denuncia no es visible para los demás estudiantes."
            ),
            ephemeral=True
        )

    else:

        if interaction.channel_id == CANAL_DENUNCIAS_ID:

            await interaction.followup.send(
                (
                    "Tu denuncia fue enviada correctamente "
                    "a los representantes.\n\n"
                    "La denuncia no es visible para los demás estudiantes."
                ),
                ephemeral=True
            )

        else:

            await interaction.followup.send(
                (
                    "Mensaje publicado sin mostrar tu identidad "
                    "al resto del servidor.\n\n"
                    "**Privacidad:** tu usuario y el contenido "
                    "quedan registrados en un canal privado "
                    "de moderación para seguridad y gestión de abusos."
                ),
                ephemeral=True
            )


@bot.event
async def on_ready():
    print("=" * 50)
    print(f"Bot conectado como: {bot.user}")
    print("=" * 50)


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
):
    if isinstance(error, app_commands.MissingPermissions):
        mensaje = "No tienes permisos suficientes para ejecutar este comando."
    else:
        print(f"Error en comando: {repr(error)}")
        mensaje = "Ocurrió un error al ejecutar el comando. Revisa los logs del bot."

    try:
        if interaction.response.is_done():
            await interaction.followup.send(mensaje, ephemeral=True)
        else:
            await interaction.response.send_message(mensaje, ephemeral=True)
    except discord.HTTPException:
        pass


bot.run(TOKEN)
