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

def find_best_qa_match(user_question, qa_data):
    """Find the best matching Q&A from training data with improved accuracy"""
    user_norm = normalize_text(user_question)
    user_words = set(user_norm.split())
    
    best_match = None
    best_score = 0
    
    for category in qa_data.values():
        for qa in category:
            # Check similarity with question
            q_score = similarity(user_norm, normalize_text(qa['question']))
            
            # Check keyword matches with word boundaries
            keyword_score = 0
            keyword_matches = 0
            for keyword in qa.get('keywords', []):
                keyword_norm = normalize_text(keyword)
                keyword_words = set(keyword_norm.split())
                
                # Exact phrase match (higher weight)
                if keyword_norm in user_norm:
                    keyword_score += 0.5
                    keyword_matches += 1
                # Word overlap match (lower weight)
                elif keyword_words & user_words:
                    keyword_score += 0.2
                    keyword_matches += 0.5
            
            # Boost score if multiple keywords match
            if keyword_matches >= 2:
                keyword_score *= 1.5
            
            total_score = q_score + keyword_score
            
            if total_score > best_score:
                best_score = total_score
                best_match = qa
    
    # Return match if score is good enough (increased threshold)
    if best_score > 0.5:
        return best_match['answer'], best_score
    
    return None, 0

def calculate_master_stats(master_data, parcours_name):
    """Calculate statistics for a master program"""
    for master in master_data:
        if parcours_name.lower() in master.get('Parcours', '').lower() or \
           parcours_name.lower() in master.get('Mention', '').lower():
            
            stats = {
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
    """Generate intelligent response with improved accuracy"""
    question_lower = user_question.lower()
    question_norm = normalize_text(user_question)
    question_words = set(question_norm.split())
    
    # Try to find match in Q&A training data first
    qa_answer, qa_score = find_best_qa_match(user_question, qa_data)
    if qa_answer and qa_score > 0.7:
        return f"<strong>✅ Réponse:</strong><br><br>{qa_answer}"
    
    # Greetings (check first to avoid false matches)
    greeting_words = ['ahla', 'salam', 'aslema', 'labes', 'chnahwelek', 'aychek', 'bonjour', 'salut', 'hello', 'hi']
    if any(word in question_lower for word in greeting_words) and len(question_words) <= 3:
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
    
    # Specific checks for better accuracy
    
    # Licences - must have "licence" keyword and NOT "master"
    if ('licence' in question_lower or 'bachelor' in question_lower) and 'master' not in question_lower:
        # Check if asking for list/types
        if any(word in question_lower for word in ['quel', 'citer', 'liste', 'disponible', 'type']):
            pres = all_data.get('presentation', {}).get('Presentation', {})
            licences = pres.get('Formations', {}).get('Licences', [])
            if licences:
                lic_list = "<br>".join([f"• {lic}" for lic in licences])
                return f"""
                <strong>🎓 Licences disponibles à l'ISSAT Kairouan:</strong><br><br>
                {lic_list}<br><br>
                💡 Veux-tu plus de détails sur une licence spécifique?
                """
        
        # Check if asking for specific licence details
        if 'informatique' in question_lower or 'isi' in question_lower:
            if any(word in question_lower for word in ['cours', 'module', 'matiere', 'programme']):
                return """
                <strong>📚 Licence en Ingénierie des Systèmes Informatiques:</strong><br><br>
                <strong>Modules principaux:</strong><br>
                • Programmation (C, Java, Python)<br>
                • Bases de données<br>
                • Réseaux informatiques<br>
                • Systèmes d'exploitation<br>
                • Génie logiciel<br>
                • Intelligence artificielle<br>
                • Développement web<br>
                • Sécurité informatique<br><br>
                <strong>Durée:</strong> 6 semestres (3 ans)<br>
                <strong>Total:</strong> 180 crédits<br><br>
                💡 Veux-tu plus de détails sur un semestre spécifique?
                """
    
    # Masters - must have "master" keyword
    if 'master' in question_lower and 'automatique' not in question_lower and 'data science' not in question_lower:
        # Check if asking for list/types
        if any(word in question_lower for word in ['quel', 'citer', 'liste', 'disponible', 'type', 'programme']):
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
            
            response += "💡 Veux-tu plus de détails sur un master spécifique?"
            return response
    
    # Organigramme - specific check
    if 'organigramme' in question_lower or ('structure' in question_lower and 'administrative' in question_lower):
        pres = all_data.get('presentation', {}).get('Presentation', {})
        directeur = pres.get('Direction', {}).get('Directeur', 'Non disponible')
        sec_gen = pres.get('Direction', {}).get('Secretaire_general', 'Non disponible')
        
        return f"""
        <strong>🏛️ Structure Administrative de l'ISSAT Kairouan:</strong><br><br>
        <strong>Direction:</strong><br>
        • Directeur: {directeur}<br>
        • Secrétaire Général: {sec_gen}<br><br>
        <strong>Départements:</strong><br>
        • Département Informatique<br>
        • Département Génie Mécanique<br>
        • Département Génie Énergétique<br>
        • Département Électronique, Électrotechnique & Automatique<br><br>
        <strong>Services:</strong><br>
        • Service Scolarité<br>
        • Service des Stages<br>
        • Service Financier<br>
        • Bibliothèque<br><br>
        💡 Veux-tu plus de détails sur un département?
        """
    
    # Coefficient - specific check
    if 'coefficient' in question_lower and 'master' not in question_lower:
        return """
        <strong>📊 Système de Coefficients à l'ISSAT:</strong><br><br>
        Les coefficients sont utilisés pour calculer la moyenne générale.<br><br>
        <strong>Pour connaître le coefficient d'une matière spécifique:</strong><br>
        • Précise le nom de la matière<br>
        • Précise le programme (Licence ou Master)<br>
        • Précise le semestre<br><br>
        <strong>Exemple:</strong> "Quel est le coefficient de Programmation C en licence informatique?"<br><br>
        💡 Quelle matière t'intéresse?
        """
    
    # Master Automatique detailed questions
    if 'automatique' in question_lower or 'informatique industrielle' in question_lower:
        master_data = all_data.get('master_recherche', [])
        stats = calculate_master_stats(master_data, 'automatique')
        
        if stats:
            # TP hours question
            if any(word in question_lower for word in ['tp', 'travaux pratiques', 'pratique']):
                if any(word in question_lower for word in ['semestre 1', 's1', 'premier']):
                    sem1 = stats['semesters'][0]
                    return f"""
                    <strong>📊 Heures de TP - Semestre 1 (Master Automatique):</strong><br><br>
                    <strong>Total TP Semestre 1:</strong> {sem1['tp_hours']} heures<br><br>
                    <strong>Détail des ateliers:</strong><br>
                    {'<br>'.join([f"• {ue['nom']}: {sum([ecue['tp'] for ecue in ue['ecues']])}h" for ue in sem1['ues'] if sum([ecue['tp'] for ecue in ue['ecues']]) > 0])}<br><br>
                    💡 Veux-tu les détails d'un autre semestre?
                    """
                elif any(word in question_lower for word in ['semestre 2', 's2', 'deuxième']):
                    sem2 = stats['semesters'][1]
                    return f"""
                    <strong>📊 Heures de TP - Semestre 2 (Master Automatique):</strong><br><br>
                    <strong>Total TP Semestre 2:</strong> {sem2['tp_hours']} heures<br><br>
                    <strong>Détail des ateliers:</strong><br>
                    {'<br>'.join([f"• {ue['nom']}: {sum([ecue['tp'] for ecue in ue['ecues']])}h" for ue in sem2['ues'] if sum([ecue['tp'] for ecue in ue['ecues']]) > 0])}<br><br>
                    💡 Veux-tu les détails d'un autre semestre?
                    """
                else:
                    return f"""
                    <strong>📊 Heures de TP - Master Automatique (Total):</strong><br><br>
                    <strong>Total TP sur tous les semestres:</strong> {stats['total_tp_hours']} heures<br><br>
                    <strong>Par semestre:</strong><br>
                    {'<br>'.join([f"• Semestre {sem['numero']}: {sem['tp_hours']}h" for sem in stats['semesters'][:3]])}<br><br>
                    💡 Veux-tu le détail d'un semestre spécifique?
                    """
            
            # Cours/TD hours
            if any(word in question_lower for word in ['cours', 'td', 'heures cours', 'volume horaire']):
                if any(word in question_lower for word in ['semestre 1', 's1']):
                    sem1 = stats['semesters'][0]
                    return f"""
                    <strong>📚 Volume horaire - Semestre 1:</strong><br><br>
                    • Cours magistral: {sem1['cours_hours']}h<br>
                    • TD: {sem1['td_hours']}h<br>
                    • TP: {sem1['tp_hours']}h<br>
                    • <strong>Total présentiel: {sem1['volume_horaire']}h</strong><br><br>
                    💡 Besoin d'autres détails?
                    """
            
            # Credits question
            if any(word in question_lower for word in ['crédit', 'credit', 'ects']):
                return f"""
                <strong>🎓 Crédits - Master Automatique:</strong><br><br>
                <strong>Total master:</strong> {stats['total_credits']} crédits<br><br>
                <strong>Par semestre:</strong><br>
                {'<br>'.join([f"• Semestre {sem['numero']}: {sem['credits']} crédits" for sem in stats['semesters']])}<br><br>
                💡 Veux-tu le détail des crédits par matière?
                """
            
            # Semester courses
            if any(word in question_lower for word in ['semestre', 'cours du']):
                for i, sem in enumerate(stats['semesters'][:3], 1):
                    if f'semestre {i}' in question_lower or f's{i}' in question_lower:
                        ues_list = '<br>'.join([
                            f"<strong>{ue['nom']}</strong> ({ue['credits']} crédits):<br>" +
                            '<br>'.join([f"  • {ecue['nom']}" for ecue in ue['ecues']])
                            for ue in sem['ues']
                        ])
                        return f"""
                        <strong>📚 Cours Semestre {i} - Master Automatique:</strong><br><br>
                        {ues_list}<br><br>
                        <strong>Total:</strong> {sem['credits']} crédits, {sem['volume_horaire']}h<br><br>
                        💡 Veux-tu plus de détails sur une matière?
                        """
    
    # Director - specific check
    if 'directeur' in question_lower or 'director' in question_lower:
        pres = all_data.get('presentation', {}).get('Presentation', {})
        directeur = pres.get('Direction', {}).get('Directeur', 'Non disponible')
        sec_gen = pres.get('Direction', {}).get('Secretaire_general', 'Non disponible')
        return f"""
        <strong>👨‍💼 Direction de l'ISSAT Kairouan:</strong><br><br>
        <strong>Directeur:</strong> {directeur}<br>
        <strong>Secrétaire Général:</strong> {sec_gen}<br><br>
        💡 Besoin d'autres informations?
        """
    
    # Attestation de présence - specific check
    if 'attestation' in question_lower and 'présence' in question_lower or 'attestation presence' in question_lower:
        procedures = all_data.get('admin_procedures', [])
        for proc in procedures:
            if proc.get('id') == 'attestation_presence':
                steps = '<br>'.join(proc.get('steps', []))
                docs = '<br>'.join([f"• {doc}" for doc in proc.get('documents', [])])
                conditions = '<br>'.join([f"• {cond}" for cond in proc.get('conditions', [])])
                return f"""
                <strong>📋 Attestation de Présence:</strong><br><br>
                <strong>Description:</strong> {proc.get('description', '')}<br><br>
                <strong>Procédure:</strong><br>{steps}<br><br>
                <strong>Documents requis:</strong><br>{docs}<br><br>
                <strong>Conditions:</strong><br>{conditions}<br><br>
                <strong>Délai:</strong> {proc.get('deadlines', '')}<br>
                <strong>Coût:</strong> {proc.get('cost', '')}<br>
                <strong>Bureau:</strong> {proc.get('office', '')}<br><br>
                <strong>Note:</strong> {proc.get('notes', '')}
                """
    
    # Réclamation détaillée - specific check
    if 'réclamation' in question_lower or 'reclamation' in question_lower:
        if 'note' in question_lower:
            procedures = all_data.get('admin_procedures', [])
            for proc in procedures:
                if proc.get('id') == 'reclamation_notes':
                    steps = '<br>'.join(proc.get('steps', []))
                    docs = '<br>'.join([f"• {doc}" for doc in proc.get('documents', [])])
                    notes = '<br>'.join([f"• {note}" for note in proc.get('important_notes', [])])
                    motifs = '<br>'.join([f"• {motif}" for motif in proc.get('motifs_reclamation', [])])
                    return f"""
                    <strong>📋 Réclamation de Note:</strong><br><br>
                    <strong>Description:</strong> {proc.get('description', '')}<br><br>
                    <strong>Procédure:</strong><br>{steps}<br><br>
                    <strong>Documents requis:</strong><br>{docs}<br><br>
                    <strong>Délai:</strong> {proc.get('deadlines', '')}<br>
                    <strong>Coût:</strong> {proc.get('cost', '')}<br><br>
                    <strong>⚠️ Points importants:</strong><br>{notes}<br><br>
                    <strong>Motifs valables:</strong><br>{motifs}
                    """
    
    # Absence rules - specific check
    if 'absence' in question_lower or 'absent' in question_lower or 'justif' in question_lower:
        rules = all_data.get('absences_rules', {})
        return f"""
        <strong>📋 Règles d'absence:</strong><br><br>
        <strong>Différence:</strong><br>{rules.get('difference', '').replace(chr(10), '<br>')}<br><br>
        <strong>Comment justifier:</strong><br>{rules.get('submit_how', '').replace(chr(10), '<br>')}<br><br>
        <strong>Délais:</strong> {rules.get('deadlines', '')}<br><br>
        <strong>⚠️ Avertissement:</strong> {rules.get('warning_logic', '')}<br><br>
        <strong>❌ Élimination:</strong> {rules.get('elimination_logic', '')}
        """
    
    # ISSAT info - specific check
    if 'issat' in question_lower or 'institut' in question_lower or 'creation' in question_lower or 'créé' in question_lower or 'fondation' in question_lower:
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
    
    # If Q&A match exists but score is medium, return it with disclaimer
    if qa_answer and qa_score > 0.5:
        return f"<strong>💡 Je pense que tu demandes:</strong><br><br>{qa_answer}<br><br><em>Si ce n'est pas ce que tu cherchais, reformule ta question!</em>"
    
    # Default fallback with better suggestions
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
    "enseignant.json", "licence.json", "licence_details.json", "master_professionnelle.json",
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
                    <input type="text" name="q" placeholder="Ex: Combien d'heures de TP en automatique?" required>
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
