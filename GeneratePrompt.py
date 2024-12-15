import os
import tiktoken

IGNORE_PATTERNS = {
    'target',
    '.git',
    '.github',
    '.idea',
    'node_modules',
    '.m2',
    '__pycache__',
    'build',
    'dist',
    'out',
}

# Eine erweiterte Sammlung relevanter Dateiendungen + Namen
RELEVANT_ENDINGS = (
    # Haupt-Quellcode (Java, Kotlin, Groovy, JSP, JS, etc.)
    '.java', '.jsp', '.kt', '.groovy', '.js', '.jsx',

    # Config / Resources
    '.xml', '.properties', '.yml', '.yaml', '.json', '.toml',

    # Build-Konfiguration
    '.gradle', '.mvn', '.gitignore', '.md',

    # Dokubestände
    '.md', '.adoc', '.rst',
)

# Oft verwendete Build-/Config-Dateien 
SPECIAL_BUILD_FILES = {
    'pom.xml',
    'build.gradle',
    'settings.gradle',
    'Dockerfile',
    'docker-compose.yml',
    'docker-compose.yaml',
}

def build_directory_tree_local(base_path, indent=0, file_paths=None):
    """
    Rekursive Funktion, die die lokale Ordnerstruktur aufbaut,
    und jene Dateien, die für den Prompt relevant sind, erfasst.
    
    :param base_path: Absoluter oder relativer Pfad zu dem Ordner, von dem aus die Suche starten soll
    :param indent: Wird benutzt, um die Ebenentiefe zu "visualisieren" (z.B. Einrückungen).
    :param file_paths: Liste, die Pfade relevanter Dateien zwischenspeichert
    :return: (tree_str, file_paths)
    """
    if file_paths is None:
        file_paths = []
    tree_str = ""

    # Inhalt des Verzeichnisses lesen
    try:
        entries = os.listdir(base_path)
    except (NotADirectoryError, PermissionError):
        return "", file_paths

    entries.sort()
    for entry in entries:
        full_path = os.path.join(base_path, entry)
        
        # Prüfe, ob wir den Pfad ignorieren (z.B. .git, target etc.)
        should_ignore = any(pattern in full_path.split(os.sep) for pattern in IGNORE_PATTERNS)
        if should_ignore:
            continue
        
        if os.path.isdir(full_path):
            tree_str += '    ' * indent + f"[{entry}/]\n"
            subtree_str, file_paths = build_directory_tree_local(full_path, indent + 1, file_paths)
            tree_str += subtree_str
        else:
            tree_str += '    ' * indent + f"{entry}\n"
            
            # Optional: Für bestimmte Build/Config-Dateien
            # direkt hoch priorisieren -> z.B. extra Label
            # (hier nur ein illustratives Beispiel für die Ausgabe)
            if entry in SPECIAL_BUILD_FILES:
                file_paths.append((indent, full_path, "BUILD_CONFIG"))
                continue
            
            # Ansonsten schauen wir uns alle relevanten Endungen an
            if entry.endswith(RELEVANT_ENDINGS):
                # Tests speziell kennzeichnen? (wenn /test/ im Pfad)
                if 'test' in full_path.lower().split(os.sep):
                    file_paths.append((indent, full_path, "TEST"))
                else:
                    file_paths.append((indent, full_path, "SOURCE"))
                
    return tree_str, file_paths


def get_local_file_content(file_path):
    """
    Liest den Inhalt einer Datei im UTF-8-Format.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        return "Binary or non-UTF8 file, cannot display text content."
    except Exception as e:
        return f"Error reading file: {str(e)}"


def retrieve_local_repo_info(base_path):
    """
    Traversiert das lokale Verzeichnis und erzeugt
    einen Prompt-ähnlichen Ausgabetext inkl. Build-/Konfigurationsdateien,
    Source-Files und ggf. Tests.
    """
    # Prüfe auf README
    readme_content = None
    for possible_readme in ("README.md", "README.MD"):
        readme_path = os.path.join(base_path, possible_readme)
        if os.path.exists(readme_path):
            readme_content = get_local_file_content(readme_path)
            break
    
    if readme_content:
        formatted_string = f"{possible_readme}:\n```\n{readme_content}\n```\n\n"
    else:
        formatted_string = "README.md: Not found!\n\n"
    
    # Verzeichnisstruktur und relevante Dateien aufbauen
    directory_tree, file_paths = build_directory_tree_local(base_path)
    formatted_string += f"Directory Structure:\n{directory_tree}\n"

    # Dateiinhalte ergänzen: 
    # Kleine Untersektionen für Build-Konfig, Source, Test
    build_section = []
    source_section = []
    test_section = []

    for indent, path, kind in file_paths:
        file_content = get_local_file_content(path)
        relative_path = os.path.relpath(path, base_path)
        snippet = (
            '\n' + '    ' * indent + f"{relative_path}:\n"
            + '    ' * indent + '```\n' + file_content + '\n' + '    ' * indent + '```\n'
        )
        
        if kind == "BUILD_CONFIG":
            build_section.append(snippet)
        elif kind == "TEST":
            test_section.append(snippet)
        else:  # "SOURCE"
            source_section.append(snippet)
    
    # Nun bauen wir das „finale Prompt“ auf
    if build_section:
        formatted_string += "\n=== Build & Config Files ===\n"
        formatted_string += "".join(build_section)
    
    if source_section:
        formatted_string += "\n=== Source Files ===\n"
        formatted_string += "".join(source_section)
    
    if test_section:
        formatted_string += "\n=== Test Files ===\n"
        formatted_string += "".join(test_section)
    
    return formatted_string


def count_tokens(prompt_text, model="gpt-3.5-turbo"):
    """
    Zählt die Anzahl der Tokens in prompt_text für das angegebene Modell.
    Default: "gpt-3.5-turbo".
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(prompt_text)
    return len(tokens)


if __name__ == "__main__":
    # Beispiel: Pfad zu deinem lokalen Java/Kotlin/Groovy-Projekt
    base_folder = r"C:\Users\Matth\OneDrive\Desktop\SpringCaching"

    # Prompt generieren
    formatted_repo_info = retrieve_local_repo_info(base_folder)

    # Token-Anzahl ermitteln
    token_count = count_tokens(formatted_repo_info, model="gpt-3.5-turbo") 
    print(f"Token Count: {token_count}")

    # In eine Datei schreiben
    output_file_name = "local-java-prompt.txt"
    with open(output_file_name, 'w', encoding='utf-8') as f:
        f.write(formatted_repo_info)

    print(f"Projektinformationen wurden in '{output_file_name}' gespeichert.")
    print(f"Das generierte Prompt hat ca. {token_count} Tokens.")
