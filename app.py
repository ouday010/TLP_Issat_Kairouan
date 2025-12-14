import streamlit as st
import io
import nltk 
from pypdf import PdfReader
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from sumy.nlp.stemmers import Stemmer

# --- Configuration de la page Streamlit ---
st.set_page_config(
    page_title="🎓 Synthèse de Cours Local (Sumy)",
    layout="wide"
)

# --- Initialisation des Dépendances NLTK ---
@st.cache_resource
def download_nltk_resources():
    """Télécharge les ressources NLTK 'punkt' nécessaires à Sumy pour le français."""
    try:
        # st.toast("Vérification et téléchargement des dépendances linguistiques NLTK...", icon="🛠️")
        nltk.download('punkt', quiet=True)
        nltk.download('punkt_tab', quiet=True) 
        return True
    except Exception as e:
        st.error(f"Erreur lors du téléchargement des ressources NLTK. Détails : {e}")
        return False

if not download_nltk_resources():
    st.stop()
else:
    st.sidebar.success("✅ Dépendances linguistiques NLTK chargées.")

# --- Constantes et Configuration ---
LANGUAGE = "french"
SENTENCES_COUNT = 10 
STEMMER = Stemmer(LANGUAGE)

# --- Fonction d'Extraction de Texte ---
@st.cache_data
def extract_text_from_pdf(uploaded_file):
    """Extrait tout le texte d'un fichier PDF."""
    st.info("Extraction du texte à partir du PDF...")
    try:
        reader = PdfReader(io.BytesIO(uploaded_file.read()))
        text = ""
        for page_num, page in enumerate(reader.pages):
            text += page.extract_text() or f" [PAGE {page_num + 1} SANS TEXTE] "
        
        if len(text.strip()) < 100:
             st.error("Le PDF semble être basé sur des images (scanné) et ne contient pas de texte lisible. Veuillez utiliser un PDF avec du texte sélectionnable.")
             return None
        
        return text
    except Exception as e:
        st.error(f"Erreur fatale lors de l'extraction du texte : {e}")
        return None

# --- Fonction de Résumé (Sumy) ---
def summarize_text_with_sumy(text, sentences_count=SENTENCES_COUNT):
    """Utilise l'algorithme LSA de Sumy pour générer un résumé extractif."""
    parser = PlaintextParser.from_string(text, Tokenizer(LANGUAGE))
    summarizer = LsaSummarizer(STEMMER)
    summary_sentences = summarizer(parser.document, sentences_count)
    
    # Retourne une liste Python des phrases. Streamlit les affichera mieux ainsi.
    summary_list = [str(sentence) for sentence in summary_sentences]
    return summary_list # ON RETOURNE UNE LISTE, PAS UNE CHAÎNE

# --- Interface Utilisateur (UX) Streamlit (Mobile Friendly) ---
def main():
    st.markdown("<h1 style='text-align: center;'>📚 Synthèse de Cours Local (Sumy)</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Solution rapide et locale (sans API) pour résumer vos PDF.</p>", unsafe_allow_html=True)

    st.markdown("---") 

    # 1. Widget de téléversement
    with st.container(border=True):
        uploaded_file = st.file_uploader("➡️ 1. Choisissez votre fichier PDF de cours", type="pdf")
    
    if uploaded_file is not None:
        st.success(f"Fichier chargé : **{uploaded_file.name}**")
        
        # 2. Paramètres du Résumé
        st.subheader("2. Paramètres du Résumé")
        sentences_count_slider = st.slider(
            "Nombre d'idées/phrases clés souhaitées :",
            min_value=5, max_value=25, value=SENTENCES_COUNT, step=1
        )
        
        st.markdown("---")
        
        # 3. Bouton d'action centré et clair
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🚀 Générer le Résumé du Cours", use_container_width=True):
                
                # --- Étape 1 : Extraction ---
                text_content = extract_text_from_pdf(uploaded_file)
                
                if not text_content:
                    return
                
                # --- Étape 2 : Résumé ---
                with st.spinner(f"⏳ L'algorithme LSA sélectionne les {sentences_count_slider} phrases les plus importantes..."):
                    # summary_result est désormais une LISTE de phrases
                    summary_list = summarize_text_with_sumy(text_content, sentences_count_slider)
                
                # --- Étape 3 : Affichage du Résultat ---
                st.subheader("✅ Résultat de la Synthèse")
                
                st.info("""
                **Rappel :** Ce résumé est **extractif** (il ne réécrit pas le texte). Il est très rapide mais n'a pas la qualité d'une IA (LLM).
                """)
                
                st.markdown(
                    f"#### Résumé Final ({sentences_count_slider} points clés) :", 
                    unsafe_allow_html=True
                )
                
                # NOUVEL AFFICHAGE : Utilisation de st.markdown avec une liste non ordonnée
                st.markdown(
                    f'<div style="border: 1px solid #ddd; padding: 15px; border-radius: 5px; background-color: #f9f9f9; color: #333;"><ul>' 
                    + "".join([f'<li>{phrase}</li>' for phrase in summary_list]) 
                    + '</ul></div>',
                    unsafe_allow_html=True
                )
                st.balloons() 

    # Footer
    st.markdown("---")
    st.caption("Ce projet est un prototype simple pour localhost. Pour une intégration web professionnelle (React), il faudrait une architecture API (FastAPI) pour le back-end Python.")


if __name__ == "__main__":
    main()