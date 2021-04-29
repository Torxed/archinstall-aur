import archinstall

class PluginHandler():
	def on_pacstrap(self, packages :list) -> list:
		print(f"Dealing with AUR packages: {packages}")

		# Returns a curated list of packages that exludes any AUR packages.
		# This allows installation.pacstrap() to contain AUR packages,
		# but won't handle them or try to install them since we remove those here.
		return packages

def install_aur_packages(*packages):
	if len(packages) == 1 and type(packages[0]) == list:
		packages = packages[0]
	elif len(packages) == 1 and type(packages[0]) == str:
		packages = packages[0].split(' ')

	print('Installing AUR packages:', packages)

# Example function injection
archinstall.install_aur_packages = install_aur_packages
archinstall.plugins['AUR'] = PluginHandler()