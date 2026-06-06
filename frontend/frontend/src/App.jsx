
//import { useState, useEffect } from "react";
//import LoginPage from "./components/LoginPage";
//import ChatWindow from "./components/ChatWindow";
//
//export default function App() {
//  const [authenticated, setAuthenticated] = useState(null);
//
//  useEffect(() => {
//    fetch("http://127.0.0.1:8000/auth/status")
      //.then(r => r.json())
      //.then(data => {
//        setAuthenticated(data.authenticated);
      //})
      //.catch(() => setAuthenticated(false));
  //}, []);
//
  // Still checking
  //if (authenticated === null) {
//  
    //return (
//      <div style={{
        //display: "flex", alignItems: "center",
        //justifyContent: "center", height: "100vh"
      //}}>
//        <div style={{ color: "#666" }}>Loading...</div>
      //</div>
    //);
  //}
//
//  return authenticated
    //? <ChatWindow onLogout={() => setAuthenticated(false)} />
    //: <LoginPage onLogin={() => setAuthenticated(true)} />;
//}
import ChatWindow from "./components/ChatWindow";

export default function App() {
  return <ChatWindow onLogout={() => {}} />;
}