import archinstall
import urllib.request
import urllib.error

__version__ = 0.2

class Plugin():
	def on_pacstrap(self, packages :list) -> list:
		if type(packages) == str:
			packages = packages.split(' ')

		print(f"Identifying AUR packages in package list: {packages}")
		aur_packages = []
		non_aur_packages = []

		# There really should be a OPTIONS pre-flight allowed here to check if the page exists.
		# Or a JSON endpoint that doesn't have the same load on the search server.
		# Dunking down the whole page just to get the status code waste about
		# ~200ms of loading time on Arch's end. But this is the most reliable
		# way for now to find an AUR package. I'll try to contribute to aur.al.org later.
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

		# ... do AUR work on the packages ...

		# Returns a curated list of packages that exludes any AUR packages.
		# This allows installataion.pacstrap() to contain AUR packages,
		# but won't handle them or try to install them since we remove those here.
		return non_aur_packages

def dummy_example(*args, **kwargs):
	pass

# Example function injection
archinstall.plugin_function = dummy_example