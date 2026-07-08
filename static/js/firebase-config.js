// TODO: Replace this with your actual Firebase config object
// 1. Go to Firebase Console -> Project Settings -> General
// 2. Scroll down to "Your apps" and copy the config object
const firebaseConfig = {
    apiKey: "AIzaSyDxBaHpRx2diSXoSkGJIm4fO-mWCCHZGH0",
    authDomain: "contentmonitor.firebaseapp.com",
    projectId: "contentmonitor",
    storageBucket: "contentmonitor.firebasestorage.app",
    messagingSenderId: "431156610761",
    appId: "1:431156610761:web:af4fe5b883d853b8566f18",
    measurementId: "G-LV71L39VS9"
};

// Initialize Firebase
if (firebaseConfig.apiKey !== "YOUR_API_KEY") {
    firebase.initializeApp(firebaseConfig);
    const db = firebase.firestore();
    window.db = db;
} else {
    console.warn("⚠️ Firebase is not configured! Dashboard will not pull data from the cloud.");
    window.db = null;
}
