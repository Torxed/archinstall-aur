import archinstall
import re
import glob
import shutil
import pathlib
import logging
import urllib.request
import urllib.error

__version__ = 0.2

sudo_user = archinstall.arguments.get('aur-user', 'aoffline_usr')
try:
	found_aur_user = archinstall.SysCommand(f"id {sudo_user}").exit_code == 0
except:
	found_aur_user = False

AUR_USER_CREATED = False

def untar_file(file):
	archinstall.log(f"(runas {sudo_user}) /usr/bin/tar --directory /home/{sudo_user}/ -xvzf {file}", level=logging.DEBUG, fg="gray")
	archinstall.storage['installation_session'].arch_chroot(f"/usr/bin/tar --directory /home/{sudo_user}/ -xvzf {file}", run_as=sudo_user)

def download_file(url, destination, filename=""):
	if not (dst := pathlib.Path(destination)).exists():
		dst.mkdir(parents=True)

	if dst.is_file():
		return False

	tmp_filename, headers = urllib.request.urlretrieve(url)
	shutil.move(tmp_filename, f"{destination}/{filename}")

	return True

class Plugin():
	def on_pacstrap(self, packages :list) -> list:
		global AUR_USER_CREATED

		if type(packages) == str:
			packages = packages.split(' ')

		archinstall.log(f"Identifying AUR packages in package list: {packages}", level=logging.INFO, fg="gray")
		aur_packages = []
		std_packages = []

		# We'd like to use upstream or a local JSON database to lookup packages.
		# But for now this is the lowest latency option that doesn't hog resources upstream.
		for package in packages:
			try:
				if archinstall.SysCommand(f"pacman -Ss {package}").exit_code == 0:
					std_packages.append(package)
				else:
					aur_packages.append(package)

			except archinstall.SysCallError:
				aur_packages.append(package)

		mount_location = archinstall.storage['installation_session'].target

		for package in aur_packages:
			if AUR_USER_CREATED is False:
				archinstall.log(f"Setting up temporary AUR build user {sudo_user} and installing build tools for {aur_packages}", level=logging.INFO, fg="gray")
				# We have to install fakeroot to the live medium as it's missing
				# (wasn't ever really intended to build stuff..)
				archinstall.storage['installation_session'].pacstrap('fakeroot', 'base-devel')

				with open(f'{mount_location}/etc/sudoers.d/{sudo_user}', 'w') as fh:
					# TODO: This could be tweaked to only contain the binaries needed, such as `makepkg` and `pacman -U`.
					# But it's done in the live environment, not the final installation..
					# So risks are low unless the user pre-enabled sshd with a login for said user.
					fh.write(f"{sudo_user} ALL=(ALL:ALL) NOPASSWD: ALL\n")

				archinstall.log(f"Creating temporary build user {sudo_user}")
				archinstall.storage['installation_session'].user_create(sudo_user, password='somethingrandom')
				# archinstall.SysCommand(f"/usr/bin/useradd -m -N -s /bin/bash {sudo_user}")

				AUR_USER_CREATED = True

			archinstall.log(f"Building AUR package {package}", level=logging.INFO, fg="yellow")
			if not download_file(f"https://aur.archlinux.org/cgit/aur.git/snapshot/{package}.tar.gz", destination=f"{mount_location}/home/{sudo_user}/", filename=f"{package}.tar.gz"):
				archinstall.log(f"Could not retrieve {package} from: https://aur.archlinux.org/cgit/aur.git/snapshot/{package}.tar.gz", fg="red", level=logging.ERROR)
				exit(1)

			archinstall.storage['installation_session'].chown(sudo_user, f"/home/{sudo_user}/{package}.tar.gz")
			untar_file(f"/home/{sudo_user}/{package}.tar.gz")
			with open(f"{mount_location}/home/{sudo_user}/{package}/PKGBUILD", 'r') as fh:
				PKGBUILD = fh.read()

			# This regexp needs to accomodate multiple keys, as well as the logic below
			gpgkeys = re.findall('validpgpkeys=\(.*\)', PKGBUILD)
			if gpgkeys:
				for key in gpgkeys:
					key = key[13:].strip('(\')"')
					archinstall.log(f"Adding GPG-key {key} to session for {sudo_user}")
					archinstall.storage['installation_session'].arch_chroot(f"/usr/bin/gpg --recv-keys {key}", run_as=sudo_user)

			if (build_handle := archinstall.storage['installation_session'].arch_chroot(f"/bin/bash -c \"cd /home/{sudo_user}/{package}; makepkg --clean --force --cleanbuild --noconfirm --needed -s\"", run_as=sudo_user)).exit_code != 0:
				archinstall.log(build_handle, level=logging.ERROR)
				archinstall.log(f"Could not build {package}, see traceback above. Continuing to avoid re-build needs for the rest of the run and re-runs.", fg="red", level=logging.ERROR)
			else:
				print(f"Looking for: {mount_location}/home/{sudo_user}/{package}/*.tar.zst")
				if (built_package := glob.glob(f"{mount_location}/home/{sudo_user}/{package}/*.tar.zst")):
					built_package = pathlib.Path(built_package[0]).name
					print(f"Found package: {built_package}")

					archinstall.storage['installation_session'].arch_chroot(f"/usr/bin/pacman --noconfirm -U /home/{sudo_user}/{package}/{built_package}")
					shutil.rmtree(f"{mount_location}/home/{sudo_user}/{package}")
					pathlib.Path(f"{mount_location}/home/{sudo_user}/{package}.tar.gz").unlink()
				else:
					archinstall.log(f"Could not locate {package}.tar.zst after build.", fg="red", level=logging.ERROR)
					exit(1)

		if AUR_USER_CREATED:
			archinstall.log(f"Removing temporary build user {sudo_user}")

			pathlib.Path(f'{mount_location}/etc/sudoers.d/{sudo_user}').unlink()

			# TODO: These are only needed if we run Installation.Boot():
			# Stop dirmngr and gpg-agent before removing home directory and running userdel
			# archinstall.storage['installation_session'].arch_chroot(f"/usr/bin/systemctl --machine={sudo_user}@.host --user stop dirmngr.socket", run_as=sudo_user)
			archinstall.storage['installation_session'].arch_chroot(f"/usr/bin/gpgconf --kill gpg-agent", run_as=sudo_user)
			try:
				archinstall.storage['installation_session'].arch_chroot(f"/usr/bin/killall -u {sudo_user}", run_as=sudo_user)
			except archinstall.SysCallError:
				# We'll terminate our own running process and that's fine
				pass
			archinstall.storage['installation_session'].arch_chroot(f"/usr/bin/userdel {sudo_user}")

			shutil.rmtree(f"{mount_location}/home/{sudo_user}")

			AUR_USER_CREATED = False

		# Returns a curated list of packages that exludes any AUR packages.
		# This allows installataion.pacstrap() to contain AUR packages,
		# but won't handle them or try to install them since we remove those here.
		return std_packages

def dummy_example(*args, **kwargs):
	pass

# Example function injection
archinstall.plugin_function = dummy_example
