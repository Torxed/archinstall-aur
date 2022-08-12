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
	archinstall.log(f"/usr/bin/sudo -H -u {archinstall.arguments.get('aur-user', 'aoffline_usr')} /usr/bin/tar --directory /home/{archinstall.arguments.get('aur-user', 'aoffline_usr')}/ -xvzf {file}", level=logging.DEBUG, fg="gray")
	archinstall.SysCommand(f"/usr/bin/sudo -H -u {archinstall.arguments.get('aur-user', 'aoffline_usr')} /usr/bin/tar --directory /home/{archinstall.arguments.get('aur-user', 'aoffline_usr')}/ -xvzf {file}")

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
		non_aur_packages = []

		#if 'base' not in packages and 'zram-generator' not in packages and 'efibootmgr' not in packages and 'pipewire' not in packages and 'nano' not in packages:
		#	exit(1)

		# There really should be a OPTIONS pre-flight allowed here.
		# Or a JSON endpoint that doesn't have the same load on the search server.
		# Dunking down the whole page just to get the status code waste about
		# ~200ms of loading time on Arch's end. But this is the most reliable
		# way for now to find an AUR package.
		for package in packages:
			try:
				request = urllib.request.urlopen(f"https://aur.archlinux.org/packages/{package}")
				status = request.status
				request.close()
			except urllib.error.HTTPError as error:
				status = error.status

			if status == 200:
				aur_packages.append(package)
			else:
				non_aur_packages.append(package)

		mount_location = archinstall.storage['installation_session'].target

		for package in aur_packages:
			if AUR_USER_CREATED is False:
				archinstall.log(f"Setting up temporary AUR build user {sudo_user} and installing build tools", level=logging.INFO, fg="gray")
				# We have to install fakeroot to the live medium as it's missing
				# (wasn't ever really intended to build stuff..)
				archinstall.storage['installation_session'].pacstrap('--noconfirm -S fakeroot base-devel')

				with open(f'/etc/sudoers.d/{sudo_user}', 'w') as fh:
					# TODO: This could be tweaked to only contain the binaries needed, such as `makepkg` and `pacman -U`.
					# But it's done in the live environment, not the final installation..
					# So risks are low unless the user pre-enabled sshd with a login for said user.
					fh.write(f"{sudo_user} ALL=(ALL:ALL) NOPASSWD: ALL\n")

				archinstall.log(f"Creating temporary build user {sudo_user}")
				archinstall.SysCommand(f"/usr/bin/useradd -m -N -s /bin/bash {sudo_user}")

				AUR_USER_CREATED = True

			archinstall.log(f"Building AUR package {package}", level=logging.INFO, fg="yellow")
			if not download_file(f"https://aur.archlinux.org/cgit/aur.git/snapshot/{package}.tar.gz", destination=f"/home/{sudo_user}/", filename=f"{package}.tar.gz"):
				archinstall.log(f"Could not retrieve {package} from: https://aur.archlinux.org/cgit/aur.git/snapshot/{package}.tar.gz", fg="red", level=logging.ERROR)
				exit(1)

			archinstall.SysCommand(f"/usr/bin/chown {sudo_user} /home/{sudo_user}/{package}.tar.gz")
			untar_file(f"/home/{sudo_user}/{package}.tar.gz")
			with open(f"/home/{sudo_user}/{package}/PKGBUILD", 'r') as fh:
				PKGBUILD = fh.read()

			# This regexp needs to accomodate multiple keys, as well as the logic below
			gpgkeys = re.findall('validpgpkeys=\(.*\)', PKGBUILD)
			if gpgkeys:
				for key in gpgkeys:
					key = key[13:].strip('(\')"')
					archinstall.log(f"Adding GPG-key {key} to session for {sudo_user}")
					archinstall.SysCommand(f"/usr/bin/sudo -H -u {sudo_user} /usr/bin/gpg --recv-keys {key}")

			if (build_handle := archinstall.SysCommand(f"/usr/bin/sudo -H -u {sudo_user} /bin/bash -c \"cd /home/{sudo_user}/{package}; makepkg --clean --force --cleanbuild --noconfirm --needed -s\"", peak_output=archinstall.arguments.get('verbose', False))).exit_code != 0:
				archinstall.log(build_handle, level=logging.ERROR)
				archinstall.log(f"Could not build {package}, see traceback above. Continuing to avoid re-build needs for the rest of the run and re-runs.", fg="red", level=logging.ERROR)
			else:
				if (built_package := glob.glob(f"/home/{sudo_user}/{package}/*.tar.zst")):
					shutil.move(built_package[0], f"{mount_location}/root/")
					archinstall.SysCommand(f"/usr/bin/chown root. {built_package[0]}")
					shutil.rmtree(f"/home/{sudo_user}/{package}")
					pathlib.Path(f"/home/{sudo_user}/{package}.tar.gz").unlink()

					archinstall.SysCommand(f"/usr/bin/arch-chroot {mount_location} sh -c 'pacman -U {built_package[0]}'")
				else:
					archinstall.log(f"Could not build {package}, see traceback above. Continuing to avoid re-build needs for the rest of the run and re-runs.", fg="red", level=logging.ERROR)

		if AUR_USER_CREATED:
			archinstall.log(f"Removing temporary build user {sudo_user}")

			pathlib.Path(f'/etc/sudoers.d/{sudo_user}').unlink()
			shutil.rmtree(f"/home/{sudo_user}")

			# Stop dirmngr and gpg-agent before removing home directory and running userdel
			archinstall.SysCommand(f"/usr/bin/systemctl --machine={sudo_user}@.host --user stop dirmngr.socket") # Doesn't do anything?
			archinstall.SysCommand(f"/usr/bin/killall -u {sudo_user}")
			archinstall.SysCommand(f"/usr/bin/sudo -H -u {sudo_user} /usr/bin/gpgconf --kill gpg-agent")
			archinstall.SysCommand(f"/usr/bin/userdel {sudo_user}")

			shutil.rmtree(f"/home/{sudo_user}")

		# Returns a curated list of packages that exludes any AUR packages.
		# This allows installataion.pacstrap() to contain AUR packages,
		# but won't handle them or try to install them since we remove those here.
		return non_aur_packages

def dummy_example(*args, **kwargs):
	pass

# Example function injection
archinstall.plugin_function = dummy_example
