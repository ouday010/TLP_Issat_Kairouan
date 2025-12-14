from flask import Flask, request, render_template_string
import os
import json
import re
from difflib import SequenceMatcher

app = Flask(__name__)

DATA_DIR = "data"

def load_json(filename):
    """Load a JSON file"""
    path = os.path.join(DATA_DIR, filename) if not filename.startswith(DATA_DIR) else filename
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def similarity(a, b):
    """Calculate similarity between two strings"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def normalize_text(text):
    """Normalize text for matching"""
    text = text.lower()
    text = re.sub(r'3', 'a', text)  # Tunisian: 3 -> a
    text = re.sub(r'[^a-z0-9\s]', '', text)
    return text

# --- NOUVELLE FONCTION 1 : EXTRAIRE LE NOM DU PROGRAMME ---
def extract_program_name(question_lower):
    """Tente d'extraire le nom du programme (Mention ou Parcours) de la question."""
    
    # Liste des mots-clés de programmes courants (à compléter avec les données réelles de l'ISSAT)
    program_keywords = [
        'automatique', 'informatique industrielle', 'reseaux', 'genie civil', 
        'genie electrique', 'telecom', 'mecanique', 'industrie', 'génie',
        'electronique', 'informatique'
    ]
    
    best_match = None
    best_score = 0.5 # Seuil minimum de confiance
    
    # 1. Extraction simple de mots-clés
    for keyword in program_keywords:
        if keyword in question_lower:
            return keyword
            
    # 2. Tentative d'extraction par regex (pour les expressions comme "master xxx")
    match = re.search(r'(master|licence)\s+(.+)', question_lower)
    if match:
        potential_name = match.group(2).strip()
        # On ne prend que les premiers mots si la phrase est longue
        potential_name = ' '.join(potential_name.split()[:3]) 

        # On vérifie si ce nom potentiel matche un des mots-clés connus
        for keyword in program_keywords:
            score = similarity(potential_name, keyword)
            if score > best_score:
                best_score = score
                best_match = keyword
                
        if best_match:
            return best_match

    # 3. Extraction de termes après des prépositions spécifiques (ex: de l')
    match_de = re.search(r'(de|du|d\'un)\s+(.+)', question_lower)
    if match_de:
        potential_name = match_de.group(2).strip().split()[0] # Ne prendre que le premier mot
        for keyword in program_keywords:
            if similarity(potential_name, keyword) > 0.7: # Seuil plus strict
                return keyword
                
    return None

# --- NOUVELLE FONCTION 2 : EXTRAIRE LE SEMESTRE ET LE TYPE D'HEURE ---
def extract_details(question_lower):
    """Extrait le semestre et le type d'heure (TP/TD/Cours) de la question."""
    
    semestre = None
    if 'semestre 1' in question_lower or 's1' in question_lower or 'premier semestre' in question_lower:
        semestre = 1
    elif 'semestre 2' in question_lower or 's2' in question_lower or 'deuxième semestre' in question_lower:
        semestre = 2
    elif 'semestre 3' in question_lower or 's3' in question_lower or 'troisième semestre' in question_lower:
        semestre = 3
    elif 'semestre 4' in question_lower or 's4' in question_lower or 'quatrième semestre' in question_lower:
        semestre = 4
        
    type_heure = None
    if any(word in question_lower for word in ['tp', 'travaux pratiques', 'pratique']):
        type_heure = 'tp'
    elif any(word in question_lower for word in ['td', 'travaux dirigés', 'dirigés']):
        type_heure = 'td'
    elif any(word in question_lower for word in ['cours', 'cours magistral', 'heures cours']):
        type_heure = 'cours'
    elif any(word in question_lower for word in ['volume horaire', 'total heures', 'heures total']):
        type_heure = 'total'
        
    return semestre, type_heure
# ----------------------------------------------------------------------


def find_best_qa_match(user_question, qa_data):
    # (Pas de changement dans cette fonction)
    """Find the best matching Q&A from training data"""
    user_norm = normalize_text(user_question)
    best_match = None
    best_score = 0
    
    for category in qa_data.values():
        for qa in category:
            # Check similarity with question
            q_score = similarity(user_norm, normalize_text(qa['question']))
            
            # Check keyword matches
            keyword_score = 0
            for keyword in qa.get('keywords', []):
                if normalize_text(keyword) in user_norm:
                    keyword_score += 0.3
            
            total_score = q_score + keyword_score
            
            if total_score > best_score:
                best_score = total_score
                best_match = qa
    
    # Return match if score is good enough
    if best_score > 0.4:
        return best_match['answer'], best_score
    
    return None, 0

def calculate_master_stats(master_data, parcours_name):
    """Calculate statistics for a master program"""
    # La logique de recherche utilise maintenant le parcours_name générique
    # La recherche est insensible à la casse et vérifie Mention ou Parcours
    for master in master_data:
        if parcours_name.lower() in master.get('Parcours', '').lower() or \
           parcours_name.lower() in master.get('Mention', '').lower():
            
            stats = {
                'title': f"Master {master.get('Parcours') or master.get('Mention')}", # Nouveau: titre pour l'affichage
                'total_credits': 0,
                'total_tp_hours': 0,
                'total_cours_hours': 0,
                'total_td_hours': 0,
                'semesters': []
            }
            
            for sem in master.get('Semestres', []):
                sem_stats = {
                    'numero': sem.get('Semestre'),
                    'credits': sem.get('Total_Credits', 0),
                    'volume_horaire': sem.get('Total_Volume_Horaire_Presentiel', 0),
                    'tp_hours': 0,
                    'cours_hours': 0,
                    'td_hours': 0,
                    'ues': []
                }
                
                for ue in sem.get('Unites_Enseignement', []):
                    ue_info = {
                        'nom': ue.get('Libelle_UE'),
                        'credits': ue.get('Cr_UE'),
                        'ecues': []
                    }
                    
                    for ecue in ue.get('ECUEs', []):
                        tp = ecue.get('TP', 0)
                        cours = ecue.get('Cours', 0)
                        td = ecue.get('TD', 0)
                        
                        sem_stats['tp_hours'] += tp
                        sem_stats['cours_hours'] += cours
                        sem_stats['td_hours'] += td
                        
                        ue_info['ecues'].append({
                            'nom': ecue.get('Libelle_ECUE'),
                            'credits': ecue.get('Cr_ECUE'),
                            'cours': cours,
                            'td': td,
                            'tp': tp
                        })
                    
                    sem_stats['ues'].append(ue_info)
                
                stats['total_credits'] += sem_stats['credits']
                stats['total_tp_hours'] += sem_stats['tp_hours']
                stats['total_cours_hours'] += sem_stats['cours_hours']
                stats['total_td_hours'] += sem_stats['td_hours']
                stats['semesters'].append(sem_stats)
            
            return stats
    
    return None

def get_smart_response(user_question, all_data, qa_data):
    """Generate intelligent response"""
    
    # =========================================================================
    #  FEUILLE DE ROUTE / FUTURES AMÉLIORATIONS (ISSAT Kairouan Chatbot)
    # =========================================================================
    # 1. 🧠 Amélioration de l'Intelligence et du Matching:
    #    - Gestion des Parfums: DONE (extract_program_name, extract_details)
    #    - Extraction de Semestre/Type d'Heure: DONE (extract_details)
    #    - Intégration d'Embedding: TO DO (Ajouter un modèle d'embedding pour similarité sémantique)
    #
    # 2. 📚 Expansion des Données et des Fonctionnalités:
    #    - Détails sur les Licences: TO DO (Implémenter calculate_licence_stats + logique de réponse)
    #    - Infos Enseignants/Responsables: TO DO (Implémenter recherche dans enseignant.json)
    #    - Procédures Administratives: TO DO (Implémenter recherche dans admin_procedures.json)
    #    - Calendrier Universitaire: TO DO (Implémenter gestion des dates/événements)
    # =========================================================================
    
    question_lower = user_question.lower()
    
    # Try to find match in Q&A training data first
    qa_answer, qa_score = find_best_qa_match(user_question, qa_data)
    if qa_answer and qa_score > 0.6:
        return f"<strong>✅ Réponse:</strong><br><br>{qa_answer}"
    
    # Greetings (Pas de changement)
    if any(word in question_lower for word in ['ahla', 'salam', 'aslema', 'labes', 'chnahwelek', 'aychek', 'bonjour', 'salut']):
        return """
        <strong>Ahla w sahla bik! 👋</strong><br>
        <strong>Labes elhamdulillah! 💙</strong><br><br>
        Ena assistant mta3 l'ISSAT Kairouan, m3allem 3la kol les données! 😊<br><br>
        <strong>💡 Njem nsa3dek fi:</strong><br>
        • Détails des programmes (Licences, Masters)<br>
        • Heures de cours, TP, TD, crédits<br>
        • Procédures administratives<br>
        • Règles d'absence<br>
        • Informations sur l'institut<br><br>
        <strong>Exemples de questions:</strong><br>
        • "Combien d'heures de TP dans le master automatique?"<br>
        • "Quels sont les cours du semestre 1?"<br>
        • "Comment justifier une absence?"<br><br>
        Qolli chnowa t7eb ta3ref! 🎓
        """
    
    # --- LOGIQUE AMÉLIÉE POUR LES QUESTIONS SUR LES PROGRAMMES ---
    
    # 1. Extraction du programme, du semestre et du type d'heure
    program_name = extract_program_name(question_lower)
    semestre_num, type_heure = extract_details(question_lower)
    
    if program_name:
        master_data = all_data.get('master_recherche', [])
        stats = calculate_master_stats(master_data, program_name)
        
        if stats:
            program_title = stats['title']
            
            # 2. Logique de réponse spécifique (TP/TD/Cours/Crédits)
            
            if type_heure == 'tp' or type_heure == 'td' or type_heure == 'cours' or type_heure == 'total':
                # Si on demande un semestre spécifique (S1, S2, S3...)
                if semestre_num and semestre_num <= len(stats['semesters']):
                    sem = stats['semesters'][semestre_num - 1]
                    
                    if type_heure == 'tp':
                        return f"""
                        <strong>📊 Heures de TP - Semestre {semestre_num} ({program_title}):</strong><br><br>
                        <strong>Total TP Semestre {semestre_num}:</strong> {sem['tp_hours']} heures<br><br>
                        <strong>Détail des ateliers:</strong><br>
                        {
                            '<br>'.join([f"• {ue['nom']}: {sum([ecue['tp'] for ecue in ue['ecues']])}h" 
                            for ue in sem['ues'] if sum([ecue['tp'] for ecue in ue['ecues']]) > 0])
                        }<br><br>
                        💡 Veux-tu le volume horaire total de ce semestre?
                        """
                        
                    elif type_heure == 'td' or type_heure == 'cours' or type_heure == 'total':
                        return f"""
                        <strong>📚 Volume horaire - Semestre {semestre_num} ({program_title}):</strong><br><br>
                        • Cours magistral: {sem['cours_hours']}h<br>
                        • TD: {sem['td_hours']}h<br>
                        • TP: {sem['tp_hours']}h<br>
                        • <strong>Total présentiel: {sem['volume_horaire']}h</strong><br><br>
                        💡 Quel est le nombre de crédits (ECTS) de ce semestre?
                        """
                
                # Si on demande le total sur le Master
                elif type_heure == 'tp':
                    return f"""
                    <strong>📊 Heures de TP - {program_title} (Total):</strong><br><br>
                    <strong>Total TP sur tous les semestres:</strong> {stats['total_tp_hours']} heures<br><br>
                    <strong>Par semestre:</strong><br>
                    {
                        '<br>'.join([f"• Semestre {sem['numero']}: {sem['tp_hours']}h" 
                        for sem in stats['semesters'][:3]])
                    }<br><br>
                    💡 Veux-tu le détail d'un semestre spécifique?
                    """
                
                elif type_heure in ['td', 'cours', 'total']:
                    return f"""
                    <strong>📚 Volume Horaire Total - {program_title}:</strong><br><br>
                    • Cours Magistral Total: {stats['total_cours_hours']}h<br>
                    • TD Total: {stats['total_td_hours']}h<br>
                    • TP Total: {stats['total_tp_hours']}h<br><br>
                    💡 Quel semestre t'intéresse le plus ?
                    """

            
            # 3. Logique de réponse pour les Crédits
            if any(word in question_lower for word in ['crédit', 'credit', 'ects']):
                return f"""
                <strong>🎓 Crédits - {program_title}:</strong><br><br>
                <strong>Total master:</strong> {stats['total_credits']} crédits<br><br>
                <strong>Par semestre:</strong><br>
                {
                    '<br>'.join([f"• Semestre {sem['numero']}: {sem['credits']} crédits" 
                    for sem in stats['semesters']])
                }<br><br>
                💡 Veux-tu le détail des crédits par matière?
                """
            
            # 4. Logique de réponse pour les Cours/Matières
            if any(word in question_lower for word in ['semestre', 'cours du', 'matières', 'ues']):
                # Si un semestre spécifique est demandé
                for i, sem in enumerate(stats['semesters'], 1):
                    if semestre_num == i:
                        ues_list = '<br>'.join([
                            f"<strong>{ue['nom']}</strong> ({ue['credits']} crédits):<br>" +
                            '<br>'.join([f"  • {ecue['nom']}" for ecue in ue['ecues']])
                            for ue in sem['ues']
                        ])
                        return f"""
                        <strong>📚 Cours Semestre {i} - {program_title}:</strong><br><br>
                        {ues_list}<br><br>
                        <strong>Total:</strong> {sem['credits']} crédits, {sem['volume_horaire']}h<br><br>
                        💡 Veux-tu plus de détails sur une matière?
                        """
                        
            # Réponse par défaut si le programme est trouvé mais la question est trop générale
            return f"""
            <strong>Master trouvé : {program_title}</strong><br><br>
            Je peux te donner le détail des heures (TP/TD/Cours) ou le nombre de crédits par semestre. 
            Sois plus précis (ex: "Heures de TP S1 en {program_name}?")
            """
    
    # --- FIN DE LA LOGIQUE AMÉLIORÉE ---
    
    # If Q&A match exists but score is medium, return it with disclaimer (Pas de changement)
    if qa_answer and qa_score > 0.4:
        return f"<strong>💡 Je pense que tu demandes:</strong><br><br>{qa_answer}<br><br><em>Si ce n'est pas ce que tu cherchais, reformule ta question!</em>"
    
    # Basic responses (Pas de changement)
    # Director
    if any(word in question_lower for word in ['directeur', 'director']):
        pres = all_data.get('presentation', {}).get('Presentation', {})
        directeur = pres.get('Direction', {}).get('Directeur', 'Non disponible')
        sec_gen = pres.get('Direction', {}).get('Secretaire_general', 'Non disponible')
        return f"""
        <strong>👨‍💼 Direction de l'ISSAT Kairouan:</strong><br><br>
        <strong>Directeur:</strong> {directeur}<br>
        <strong>Secrétaire Général:</strong> {sec_gen}<br><br>
        💡 Besoin d'autres informations?
        """
    
    # Licences
    if any(word in question_lower for word in ['licence', 'licences', 'bachelor']) and 'master' not in question_lower:
        pres = all_data.get('presentation', {}).get('Presentation', {})
        licences = pres.get('Formations', {}).get('Licences', [])
        if licences:
            lic_list = "<br>".join([f"• {lic}" for lic in licences])
            return f"""
            <strong>🎓 Licences disponibles à l'ISSAT Kairouan:</strong><br><br>
            {lic_list}<br><br>
            💡 Veux-tu plus de détails sur une licence?
            """
    
    # Masters
    if any(word in question_lower for word in ['master', 'masters', 'mastere']) and not program_name:
        pres = all_data.get('presentation', {}).get('Presentation', {})
        masters_rech = pres.get('Formations', {}).get('Masters_Recherche', [])
        masters_pro = pres.get('Formations', {}).get('Masters_Professionnels', [])
        
        response = "<strong>🎓 Masters disponibles à l'ISSAT Kairouan:</strong><br><br>"
        
        if masters_rech:
            response += "<strong>Masters Recherche:</strong><br>"
            response += "<br>".join([f"• {m}" for m in masters_rech])
            response += "<br><br>"
        
        if masters_pro:
            response += "<strong>Masters Professionnels:</strong><br>"
            response += "<br>".join([f"• {m}" for m in masters_pro])
            response += "<br><br>"
        
        response += "💡 Veux-tu plus de détails sur un master?"
        return response
    
    # Absence rules
    if any(word in question_lower for word in ['absence', 'absent', 'justif']):
        rules = all_data.get('absences_rules', {})
        return f"""
        <strong>📋 Règles d'absence:</strong><br><br>
        <strong>Différence:</strong><br>{rules.get('difference', '').replace(chr(10), '<br>')}<br><br>
        <strong>Comment justifier:</strong><br>{rules.get('submit_how', '').replace(chr(10), '<br>')}<br><br>
        <strong>Délais:</strong> {rules.get('deadlines', '')}<br><br>
        <strong>⚠️ Avertissement:</strong> {rules.get('warning_logic', '')}<br><br>
        <strong>❌ Élimination:</strong> {rules.get('elimination_logic', '')}
        """
    
    # ISSAT info
    if any(word in question_lower for word in ['issat', 'institut', 'kairouan', 'creation', 'créé']):
        pres = all_data.get('presentation', {}).get('Presentation', {})
        etab = pres.get('Etablissement', {})
        creation = pres.get('Creation', {})
        infra = pres.get('Infrastructure', {})
        
        return f"""
        <strong>🏛️ ISSAT Kairouan:</strong><br><br>
        <strong>Nom:</strong> {etab.get('Nom', '')}<br>
        <strong>Création:</strong> {creation.get('Annee', '')} ({creation.get('Decret', '')})<br>
        <strong>Capacité:</strong> {infra.get('Capacite', {}).get('Etudiants', '')} étudiants<br>
        <strong>Enseignants:</strong> {infra.get('Capacite', {}).get('Enseignants', '')}<br><br>
        💡 Veux-tu en savoir plus?
        """
    
    # Default fallback
    return """
    <strong>🤔 Je n'ai pas bien compris ta question...</strong><br><br>
    💡 <strong>Exemples de questions:</strong><br>
    • "Combien d'heures de TP dans le master automatique?"<br>
    • "Quels sont les masters disponibles?"<br>
    • "Quelles licences sont disponibles?"<br>
    • "Comment justifier une absence?"<br>
    • "Qui est le directeur?"<br><br>
    Essaie de reformuler! 😊
    """

# Load all data
print("🔄 Loading data...")
all_data = {}
files = [
    "presentation.json", "admin_procedures.json", "absences_rules.json",
    "enseignant.json", "licence.json", "master_professionnelle.json",
    "master_recherche.json", "directeur_responsable.json",
    "conseil_scientifique.json", "organigramme.json", "general_institute.json"
]

for file in files:
    data = load_json(file)
    if data:
        all_data[file.replace('.json', '')] = data
        print(f"✅ Loaded {file}")

# Load Q&A training data
qa_data = load_json("c:/Users/DELL/Desktop/Chatbot/training_qa.json")
if qa_data:
    total_qa = sum(len(category) for category in qa_data.values())
    print(f"✅ Loaded {total_qa} Q&A training examples")
else:
    qa_data = {}
    print("⚠️ No Q&A training data found")

print(f"✅ System ready with {len(all_data)} data files")

# Conversation storage
conversations = []

HTML = '''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ISSAT Kairouan - Assistant Intelligent</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.2);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            padding: 20px;
            text-align: center;
        }
        .header h1 { font-size: 1.8em; margin-bottom: 5px; }
        .header p { font-size: 0.9em; opacity: 0.9; }
        .messages {
            padding: 20px;
            min-height: 400px;
            max-height: 500px;
            overflow-y: auto;
            background: #f8f9fa;
        }
        .message {
            margin-bottom: 15px;
            padding: 15px;
            border-radius: 10px;
            line-height: 1.6;
        }
        .user { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; 
            text-align: right; 
            margin-left: 20%; 
        }
        .bot { 
            background: white; 
            color: #333; 
            border: 1px solid #e0e0e0; 
            margin-right: 20%; 
        }
        .input-form { 
            padding: 20px; 
            background: white; 
            border-top: 1px solid #eee; 
        }
        .input-group { 
            display: flex; 
            gap: 10px; 
        }
        input[type="text"] {
            flex: 1;
            padding: 15px 20px;
            border: 2px solid #e0e0e0;
            border-radius: 25px;
            font-size: 1em;
            outline: none;
        }
        input[type="text"]:focus { border-color: #4facfe; }
        button {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 25px;
            cursor: pointer;
            font-size: 1em;
            font-weight: bold;
        }
        button:hover { opacity: 0.9; }
        .welcome { 
            background: #e3f2fd; 
            color: #1976d2; 
            padding: 15px; 
            border-radius: 10px; 
            margin-bottom: 15px; 
        }

        /* Mobile responsive adjustments */
        @media screen and (max-width: 600px) {
            .container {
                width: 100%;
                border-radius: 0;
            }
            .messages {
                padding: 15px;
                max-height: 400px;
            }
            .user { 
                margin-left: 5%; 
            }
            .bot { 
                margin-right: 5%; 
            }
            input[type="text"] { 
                padding: 12px 15px; 
                font-size: 0.9em; 
            }
            button { 
                padding: 12px 20px; 
                font-size: 0.9em; 
            }
            .header h1 { font-size: 1.5em; }
            .header p { font-size: 0.8em; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 ISSAT Kairouan - Assistant Intelligent</h1>
            <p>Entraîné sur des Q&A détaillées - Comprend les questions complexes!</p>
        </div>
        <div class="messages" id="msgs">
            <div class="welcome">
                <strong>Ahla w sahla! 👋</strong><br>
                Je suis un assistant INTELLIGENT entraîné sur des Q&A détaillées!<br>
                💡 Je peux répondre à des questions précises sur les heures, crédits, cours, etc.
            </div>
            {% for msg in messages %}
            <div class="message {{msg.type}}">{{msg.content|safe}}</div>
            {% endfor %}
        </div>
        <div class="input-form">
            <form method="POST">
                <div class="input-group">
                    <input type="text" name="q" placeholder="Ex: Combien d'heures de TP dans le master automatique?" required>
                    <button type="submit">Envoyer ➤</button>
                </div>
            </form>
        </div>
    </div>
    <script>
        document.querySelector('.messages').scrollTop = 999999;
    </script>
</body>
</html>
'''

@app.route("/", methods=["GET", "POST"])
def home():
    global conversations
    
    if request.method == "POST":
        user_msg = request.form.get("q", "").strip()
        if user_msg:
            conversations.append({"type": "user", "content": user_msg})
            print(f"👤 User: {user_msg}")
            
            response = get_smart_response(user_msg, all_data, qa_data)
            conversations.append({"type": "bot", "content": response})
            print(f"🤖 Bot: Response generated")
    
    return render_template_string(HTML, messages=conversations)

if __name__ == "__main__":
    print("🚀 ISSAT Smart Chatbot Starting...")
    print("🧠 Trained on detailed Q&A examples")
    print("💡 Can answer complex questions about courses, hours, credits, etc.")
    print("🌐 Server: http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=True)
