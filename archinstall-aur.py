import archinstall

class Plugin():
	def on_pacstrap(self, packages :list) -> list:
		print(f"Identifying AUR packages in package list: {packages}")

		# ... do AUR work on the packages ...

		# Returns a curated list of packages that exludes any AUR packages.
		# This allows installation.pacstrap() to contain AUR packages,
		# but won't handle them or try to install them since we remove those here.
		return packages

def dummy_example(*args, **kwargs):
	pass

# Example function injection
archinstall.plugin_function = dummy_example()