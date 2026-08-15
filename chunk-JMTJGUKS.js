import{a as He,b as qe,d as wt}from"./chunk-LE6J2TQN.js";import{a as Le,b as Bt,g as Vt,h as $t}from"./chunk-WDTEMRH2.js";import{a as $,c as R,d as ue,f as De,g as We}from"./chunk-RR5PBDFK.js";import{c as xt,d as Ke,f as Ge,h as Ye,i as Je,k as Xe}from"./chunk-F2X3VGZZ.js";import{a as Ne,f as Mt,i as Qe,s as Ft}from"./chunk-LDSYLCUA.js";import{C as It,D as _e,E as it,H as ve,N as Ot,Q as je,R as ke,b as et,d as St,ea as kt,ka as Et,na as pe,oa as O,r as Tt,s as tt,w as ye}from"./chunk-GYVLW3BR.js";import{Ca as ot,Kb as at,Na as Ee,Ra as st,Va as ze,e as zt,la as nt,sa as Lt,ub as Dt,vb as rt,zb as lt}from"./chunk-DPWP3BQG.js";import{j as ce,k as Ct,l as Ae,m as xe,n as de,s as A,v as Oe}from"./chunk-YL4SFW5Q.js";import{$ as S,Ab as mt,Bb as gt,Cb as b,Cc as G,Db as w,Dc as Pe,Eb as F,Fb as se,Gb as re,Hb as N,Ib as ge,Jb as ft,Mb as K,Nb as p,Ob as le,Pb as ae,Qb as B,Rb as we,Sb as T,Tb as I,U as Fe,Ub as Ie,V as z,Va as h,Vb as yt,W as H,Wb as _t,_a as me,c as Ze,eb as x,fb as j,fc as V,ga as pt,gb as ut,gc as vt,ha as ie,hc as Q,ia as ne,ib as v,ic as oe,ja as X,jb as ht,jc as Re,kb as _,la as m,n as Se,nc as bt,rb as C,rc as fe,s as J,sa as L,sb as a,t as Te,ta as Be,tb as Ve,ub as ee,vb as $e,wb as E,xb as Ce}from"./chunk-46CFOLXN.js";import{a as Rt}from"./chunk-PSJ5TD5D.js";import{a as W,b as be,e as U}from"./chunk-ACKELEN3.js";var Xt=["icon"],ei=["content"],At=t=>({$implicit:t}),ti=(t,s)=>({"p-togglebutton-icon":!0,"p-togglebutton-icon-left":t,"p-togglebutton-icon-right":s});function ii(t,s){t&1&&N(0)}function ni(t,s){if(t&1&&F(0,"span",0),t&2){let e=p(3);E(e.checked?e.onIcon:e.offIcon),a("ngClass",oe(4,ti,e.iconPos==="left",e.iconPos==="right")),C("data-pc-section","icon")}}function oi(t,s){if(t&1&&_(0,ni,1,7,"span",2),t&2){let e=p(2);Ce(e.onIcon||e.offIcon?0:-1)}}function si(t,s){t&1&&N(0)}function ri(t,s){if(t&1&&_(0,si,1,0,"ng-container",1),t&2){let e=p(2);a("ngTemplateOutlet",e.iconTemplate||e._iconTemplate)("ngTemplateOutletContext",Q(2,At,e.checked))}}function li(t,s){if(t&1&&(_(0,oi,1,1)(1,ri,1,4,"ng-container"),b(2,"span",0),yt(3),w()),t&2){let e=p();Ce(e.iconTemplate?1:0),h(2),a("ngClass",e.cx("label")),C("data-pc-section","label"),h(),_t(e.checked?e.hasOnLabel?e.onLabel:"\xA0":e.hasOffLabel?e.offLabel:"\xA0")}}var ai=({dt:t})=>`
.p-togglebutton {
    display: inline-flex;
    cursor: pointer;
    user-select: none;
    overflow: hidden;
    position: relative;
    color: ${t("togglebutton.color")};
    background: ${t("togglebutton.background")};
    border: 1px solid ${t("togglebutton.border.color")};
    padding: ${t("togglebutton.padding")};
    font-size: 1rem;
    font-family: inherit;
    font-feature-settings: inherit;
    transition: background ${t("togglebutton.transition.duration")}, color ${t("togglebutton.transition.duration")}, border-color ${t("togglebutton.transition.duration")},
        outline-color ${t("togglebutton.transition.duration")}, box-shadow ${t("togglebutton.transition.duration")};
    border-radius: ${t("togglebutton.border.radius")};
    outline-color: transparent;
    font-weight: ${t("togglebutton.font.weight")};
}

.p-togglebutton-content {
    display: inline-flex;
    flex: 1 1 auto;
    align-items: center;
    justify-content: center;
    gap: ${t("togglebutton.gap")};
    padding: ${t("togglebutton.content.padding")};
    background: transparent;
    border-radius: ${t("togglebutton.content.border.radius")};
    transition: background ${t("togglebutton.transition.duration")}, color ${t("togglebutton.transition.duration")}, border-color ${t("togglebutton.transition.duration")},
            outline-color ${t("togglebutton.transition.duration")}, box-shadow ${t("togglebutton.transition.duration")};
}

.p-togglebutton:not(:disabled):not(.p-togglebutton-checked):hover {
    background: ${t("togglebutton.hover.background")};
    color: ${t("togglebutton.hover.color")};
}

.p-togglebutton.p-togglebutton-checked {
    background: ${t("togglebutton.checked.background")};
    border-color: ${t("togglebutton.checked.border.color")};
    color: ${t("togglebutton.checked.color")};
}

.p-togglebutton-checked .p-togglebutton-content {
    background: ${t("togglebutton.content.checked.background")};
    box-shadow: ${t("togglebutton.content.checked.shadow")};
}

.p-togglebutton:focus-visible {
    box-shadow: ${t("togglebutton.focus.ring.shadow")};
    outline: ${t("togglebutton.focus.ring.width")} ${t("togglebutton.focus.ring.style")} ${t("togglebutton.focus.ring.color")};
    outline-offset: ${t("togglebutton.focus.ring.offset")};
}

.p-togglebutton.p-invalid {
    border-color: ${t("togglebutton.invalid.border.color")};
}

.p-togglebutton:disabled:not(.p-togglebutton-checked) {
    opacity: 1;
    cursor: default;
    background: ${t("togglebutton.disabled.background")};
    border-color: ${t("togglebutton.disabled.border.color")};
    color: ${t("togglebutton.disabled.color")};
}

.p-togglebutton-label,
.p-togglebutton-icon {
    position: relative;
    transition: none;
}

.p-togglebutton-icon {
    color: ${t("togglebutton.icon.color")};
}

.p-togglebutton:not(:disabled):not(.p-togglebutton-checked):hover .p-togglebutton-icon {
    color: ${t("togglebutton.icon.hover.color")};
}

.p-togglebutton.p-togglebutton-checked .p-togglebutton-icon {
    color: ${t("togglebutton.icon.checked.color")};
}

.p-togglebutton:disabled .p-togglebutton-icon {
    color: ${t("togglebutton.icon.disabled.color")};
}

.p-togglebutton-sm {
    padding: ${t("togglebutton.sm.padding")};
    font-size: ${t("togglebutton.sm.font.size")};
}

.p-togglebutton-sm .p-togglebutton-content {
    padding: ${t("togglebutton.content.sm.padding")};
}

.p-togglebutton-lg {
    padding: ${t("togglebutton.lg.padding")};
    font-size: ${t("togglebutton.lg.font.size")};
}

.p-togglebutton-lg .p-togglebutton-content {
    padding: ${t("togglebutton.content.lg.padding")};
}

/* For PrimeNG (iconPos) */
.p-togglebutton-icon-right {
    order: 1;
}

.p-togglebutton.ng-invalid.ng-dirty {
    border-color: ${t("togglebutton.invalid.border.color")};
}
`,ci={root:({instance:t})=>({"p-togglebutton p-component":!0,"p-togglebutton-checked":t.checked,"p-disabled":t.disabled,"p-togglebutton-sm p-inputfield-sm":t.size==="small","p-togglebutton-lg p-inputfield-lg":t.size==="large"}),content:"p-togglebutton-content",icon:"p-togglebutton-icon",label:"p-togglebutton-label"},Pt=(()=>{class t extends ${name="togglebutton";theme=ai;classes=ci;static \u0275fac=(()=>{let e;return function(n){return(e||(e=m(t)))(n||t)}})();static \u0275prov=z({token:t,factory:t.\u0275fac})}return t})();var di={provide:Ne,useExisting:Fe(()=>ct),multi:!0},ct=(()=>{class t extends R{get hostClass(){return this.styleClass||""}onKeyDown(e){switch(e.code){case"Enter":this.toggle(e),e.preventDefault();break;case"Space":this.toggle(e),e.preventDefault();break}}toggle(e){!this.disabled&&!(this.allowEmpty===!1&&this.checked)&&(this.checked=!this.checked,this.onModelChange(this.checked),this.onModelTouched(),this.onChange.emit({originalEvent:e,checked:this.checked}),this.cd.markForCheck())}onLabel="Yes";offLabel="No";onIcon;offIcon;ariaLabel;ariaLabelledBy;disabled;style;styleClass;inputId;tabindex=0;size;iconPos="left";autofocus;allowEmpty;onChange=new L;iconTemplate;contentTemplate;templates;checked=!1;onModelChange=()=>{};onModelTouched=()=>{};_componentStyle=S(Pt);onBlur(){this.onModelTouched()}writeValue(e){this.checked=e,this.cd.markForCheck()}registerOnChange(e){this.onModelChange=e}registerOnTouched(e){this.onModelTouched=e}setDisabledState(e){this.disabled=e,this.cd.markForCheck()}get hasOnLabel(){return this.onLabel&&this.onLabel.length>0}get hasOffLabel(){return this.onLabel&&this.onLabel.length>0}get active(){return this.checked===!0}_iconTemplate;_contentTemplate;ngAfterContentInit(){this.templates.forEach(e=>{switch(e.getType()){case"icon":this._iconTemplate=e.template;break;case"content":this._contentTemplate=e.template;break;default:this._contentTemplate=e.template;break}})}static \u0275fac=(()=>{let e;return function(n){return(e||(e=m(t)))(n||t)}})();static \u0275cmp=x({type:t,selectors:[["p-toggleButton"],["p-togglebutton"],["p-toggle-button"]],contentQueries:function(i,n,o){if(i&1&&(B(o,Xt,4),B(o,ei,4),B(o,pe,4)),i&2){let r;T(r=I())&&(n.iconTemplate=r.first),T(r=I())&&(n.contentTemplate=r.first),T(r=I())&&(n.templates=r)}},hostVars:23,hostBindings:function(i,n){i&1&&K("keydown",function(r){return n.onKeyDown(r)})("click",function(r){return n.toggle(r)}),i&2&&(ft("tabindex",n.tabindex),C("disabled",n.disabled)("aria-labelledby",n.ariaLabelledBy)("aria-pressed",n.checked)("data-p-checked",n.active)("data-p-disabled",n.disabled)("type","button"),E(n.hostClass),ee("p-togglebutton",!0)("p-togglebutton-checked",n.checked)("p-disabled",n.disabled)("p-togglebutton-sm",n.size==="small")("p-inputfield-sm",n.size==="small")("p-togglebutton-lg",n.size==="large")("p-inputfield-lg",n.size==="large"))},inputs:{onLabel:"onLabel",offLabel:"offLabel",onIcon:"onIcon",offIcon:"offIcon",ariaLabel:"ariaLabel",ariaLabelledBy:"ariaLabelledBy",disabled:[2,"disabled","disabled",G],style:"style",styleClass:"styleClass",inputId:"inputId",tabindex:[2,"tabindex","tabindex",Pe],size:"size",iconPos:"iconPos",autofocus:[2,"autofocus","autofocus",G],allowEmpty:"allowEmpty"},outputs:{onChange:"onChange"},features:[V([di,Pt]),ht([$t]),v],decls:3,vars:6,consts:[[3,"ngClass"],[4,"ngTemplateOutlet","ngTemplateOutletContext"],[3,"class","ngClass"]],template:function(i,n){i&1&&(b(0,"span",0),_(1,ii,1,0,"ng-container",1)(2,li,4,4),w()),i&2&&(a("ngClass",n.cx("content")),h(),a("ngTemplateOutlet",n.contentTemplate||n._contentTemplate)("ngTemplateOutletContext",Q(4,At,n.checked)),h(),Ce(n.contentTemplate?-1:2))},dependencies:[A,ce,de,O],encapsulation:2,changeDetection:0})}return t})();var ui=["item"],hi=(t,s)=>({$implicit:t,index:s});function mi(t,s){return this.getOptionLabel(s)}function gi(t,s){t&1&&N(0)}function fi(t,s){if(t&1&&_(0,gi,1,0,"ng-container",3),t&2){let e=p(2),i=e.$implicit,n=e.$index,o=p();a("ngTemplateOutlet",o.itemTemplate||o._itemTemplate)("ngTemplateOutletContext",oe(2,hi,i,n))}}function yi(t,s){t&1&&_(0,fi,1,5,"ng-template",null,0,fe)}function _i(t,s){if(t&1){let e=ge();b(0,"p-toggleButton",2),K("onChange",function(n){let o=ie(e),r=o.$implicit,l=o.$index,g=p();return ne(g.onOptionSelect(n,r,l))}),_(1,yi,2,0),w()}if(t&2){let e=s.$implicit,i=p();a("autofocus",i.autofocus)("styleClass",i.styleClass)("ngModel",i.isSelected(e))("onLabel",i.getOptionLabel(e))("offLabel",i.getOptionLabel(e))("disabled",i.disabled||i.isOptionDisabled(e))("allowEmpty",i.getAllowEmpty())("size",i.size),h(),Ce(i.itemTemplate||i._itemTemplate?1:-1)}}var vi=({dt:t})=>`
.p-selectbutton {
    display: inline-flex;
    user-select: none;
    vertical-align: bottom;
    outline-color: transparent;
    border-radius: ${t("selectbutton.border.radius")};
}

.p-selectbutton .p-togglebutton {
    border-radius: 0;
    border-width: 1px 1px 1px 0;
}

.p-selectbutton .p-togglebutton:focus-visible {
    position: relative;
    z-index: 1;
}

.p-selectbutton .p-togglebutton:first-child {
    border-inline-start-width: 1px;
    border-start-start-radius: ${t("selectbutton.border.radius")};
    border-end-start-radius: ${t("selectbutton.border.radius")};
}

.p-selectbutton .p-togglebutton:last-child {
    border-start-end-radius: ${t("selectbutton.border.radius")};
    border-end-end-radius: ${t("selectbutton.border.radius")};
}

.p-selectbutton.ng-invalid.ng-dirty {
    outline: 1px solid ${t("selectbutton.invalid.border.color")};
    outline-offset: 0;
}
`,bi={root:({props:t})=>["p-selectbutton p-component",{"p-invalid":t.invalid}]},Ht=(()=>{class t extends ${name="selectbutton";theme=vi;classes=bi;static \u0275fac=(()=>{let e;return function(n){return(e||(e=m(t)))(n||t)}})();static \u0275prov=z({token:t,factory:t.\u0275fac})}return t})();var Ci={provide:Ne,useExisting:Fe(()=>jt),multi:!0},jt=(()=>{class t extends R{options;optionLabel;optionValue;optionDisabled;get unselectable(){return this._unselectable}_unselectable=!1;set unselectable(e){this._unselectable=e,this.allowEmpty=!e}tabindex=0;multiple;allowEmpty=!0;style;styleClass;ariaLabelledBy;size;disabled;dataKey;autofocus;onOptionClick=new L;onChange=new L;itemTemplate;_itemTemplate;get equalityKey(){return this.optionValue?null:this.dataKey}value;onModelChange=()=>{};onModelTouched=()=>{};focusedIndex=0;_componentStyle=S(Ht);getAllowEmpty(){return this.multiple?this.allowEmpty||this.value?.length!==1:this.allowEmpty}getOptionLabel(e){return this.optionLabel?je(e,this.optionLabel):e.label!=null?e.label:e}getOptionValue(e){return this.optionValue?je(e,this.optionValue):this.optionLabel||e.value===void 0?e:e.value}isOptionDisabled(e){return this.optionDisabled?je(e,this.optionDisabled):e.disabled!==void 0?e.disabled:!1}writeValue(e){this.value=e,this.cd.markForCheck()}registerOnChange(e){this.onModelChange=e}registerOnTouched(e){this.onModelTouched=e}setDisabledState(e){this.disabled=e,this.cd.markForCheck()}onOptionSelect(e,i,n){if(this.disabled||this.isOptionDisabled(i))return;let o=this.isSelected(i);if(o&&this.unselectable)return;let r=this.getOptionValue(i),l;if(this.multiple)o?l=this.value.filter(g=>!ke(g,r,this.equalityKey)):l=this.value?[...this.value,r]:[r];else{if(o&&!this.allowEmpty)return;l=o?null:r}this.focusedIndex=n,this.value=l,this.onModelChange(this.value),this.onChange.emit({originalEvent:e,value:this.value}),this.onOptionClick.emit({originalEvent:e,option:i,index:n})}changeTabIndexes(e,i){let n,o;for(let r=0;r<=this.el.nativeElement.children.length-1;r++)this.el.nativeElement.children[r].getAttribute("tabindex")==="0"&&(n={elem:this.el.nativeElement.children[r],index:r});i==="prev"?n.index===0?o=this.el.nativeElement.children.length-1:o=n.index-1:n.index===this.el.nativeElement.children.length-1?o=0:o=n.index+1,this.focusedIndex=o,this.el.nativeElement.children[o].focus()}onFocus(e,i){this.focusedIndex=i}onBlur(){this.onModelTouched()}removeOption(e){this.value=this.value.filter(i=>!ke(i,this.getOptionValue(e),this.dataKey))}isSelected(e){let i=!1,n=this.getOptionValue(e);if(this.multiple){if(this.value&&Array.isArray(this.value)){for(let o of this.value)if(ke(o,n,this.dataKey)){i=!0;break}}}else i=ke(this.getOptionValue(e),this.value,this.equalityKey);return i}templates;ngAfterContentInit(){this.templates.forEach(e=>{switch(e.getType()){case"item":this._itemTemplate=e.template;break}})}static \u0275fac=(()=>{let e;return function(n){return(e||(e=m(t)))(n||t)}})();static \u0275cmp=x({type:t,selectors:[["p-selectButton"],["p-selectbutton"],["p-select-button"]],contentQueries:function(i,n,o){if(i&1&&(B(o,ui,4),B(o,pe,4)),i&2){let r;T(r=I())&&(n.itemTemplate=r.first),T(r=I())&&(n.templates=r)}},hostVars:10,hostBindings:function(i,n){i&2&&(C("role","group")("aria-labelledby",n.ariaLabelledBy)("data-pc-section","root")("data-pc-name","selectbutton"),$e(n.style),ee("p-selectbutton",!0)("p-component",!0))},inputs:{options:"options",optionLabel:"optionLabel",optionValue:"optionValue",optionDisabled:"optionDisabled",unselectable:[2,"unselectable","unselectable",G],tabindex:[2,"tabindex","tabindex",Pe],multiple:[2,"multiple","multiple",G],allowEmpty:[2,"allowEmpty","allowEmpty",G],style:"style",styleClass:"styleClass",ariaLabelledBy:"ariaLabelledBy",size:"size",disabled:[2,"disabled","disabled",G],dataKey:"dataKey",autofocus:[2,"autofocus","autofocus",G]},outputs:{onOptionClick:"onOptionClick",onChange:"onChange"},features:[V([Ci,Ht]),v],decls:2,vars:0,consts:[["content",""],[3,"autofocus","styleClass","ngModel","onLabel","offLabel","disabled","allowEmpty","size"],[3,"onChange","autofocus","styleClass","ngModel","onLabel","offLabel","disabled","allowEmpty","size"],[4,"ngTemplateOutlet","ngTemplateOutletContext"]],template:function(i,n){i&1&&mt(0,_i,2,9,"p-toggleButton",1,mi,!0),i&2&&gt(n.options)},dependencies:[ct,Ft,Mt,Qe,A,de,O],encapsulation:2,changeDetection:0})}return t})(),so=(()=>{class t{static \u0275fac=function(i){return new(i||t)};static \u0275mod=j({type:t});static \u0275inj=H({imports:[jt,O,O]})}return t})();var wi=({dt:t})=>`
.p-progressspinner {
    position: relative;
    margin: 0 auto;
    width: 100px;
    height: 100px;
    display: inline-block;
}

.p-progressspinner::before {
    content: "";
    display: block;
    padding-top: 100%;
}

.p-progressspinner-spin {
    height: 100%;
    transform-origin: center center;
    width: 100%;
    position: absolute;
    top: 0;
    bottom: 0;
    left: 0;
    right: 0;
    margin: auto;
    animation: p-progressspinner-rotate 2s linear infinite;
}

.p-progressspinner-circle {
    stroke-dasharray: 89, 200;
    stroke-dashoffset: 0;
    stroke: ${t("progressspinner.colorOne")};
    animation: p-progressspinner-dash 1.5s ease-in-out infinite, p-progressspinner-color 6s ease-in-out infinite;
    stroke-linecap: round;
}

@keyframes p-progressspinner-rotate {
    100% {
        transform: rotate(360deg);
    }
}
@keyframes p-progressspinner-dash {
    0% {
        stroke-dasharray: 1, 200;
        stroke-dashoffset: 0;
    }
    50% {
        stroke-dasharray: 89, 200;
        stroke-dashoffset: -35px;
    }
    100% {
        stroke-dasharray: 89, 200;
        stroke-dashoffset: -124px;
    }
}
@keyframes p-progressspinner-color {
    100%,
    0% {
        stroke: ${t("progressspinner.colorOne")};
    }
    40% {
        stroke: ${t("progressspinner.colorTwo")};
    }
    66% {
        stroke: ${t("progressspinner.colorThree")};
    }
    80%,
    90% {
        stroke: ${t("progressspinner.colorFour")};
    }
}
`,xi={root:"p-progressspinner",spin:"p-progressspinner-spin",circle:"p-progressspinner-circle"},Nt=(()=>{class t extends ${name="progressspinner";theme=wi;classes=xi;static \u0275fac=(()=>{let e;return function(n){return(e||(e=m(t)))(n||t)}})();static \u0275prov=z({token:t,factory:t.\u0275fac})}return t})();var Si=(()=>{class t extends R{styleClass;style;strokeWidth="2";fill="none";animationDuration="2s";ariaLabel;_componentStyle=S(Nt);static \u0275fac=(()=>{let e;return function(n){return(e||(e=m(t)))(n||t)}})();static \u0275cmp=x({type:t,selectors:[["p-progressSpinner"],["p-progress-spinner"],["p-progressspinner"]],inputs:{styleClass:"styleClass",style:"style",strokeWidth:"strokeWidth",fill:"fill",animationDuration:"animationDuration",ariaLabel:"ariaLabel"},features:[V([Nt]),v],decls:3,vars:11,consts:[["role","progressbar",1,"p-progressspinner",3,"ngStyle","ngClass"],["viewBox","25 25 50 50",1,"p-progressspinner-spin"],["cx","50","cy","50","r","20","stroke-miterlimit","10",1,"p-progressspinner-circle"]],template:function(i,n){i&1&&(b(0,"div",0),X(),b(1,"svg",1),F(2,"circle",2),w()()),i&2&&(a("ngStyle",n.style)("ngClass",n.styleClass),C("aria-label",n.ariaLabel)("aria-busy",!0)("data-pc-name","progressspinner")("data-pc-section","root"),h(),Ve("animation-duration",n.animationDuration),C("data-pc-section","root"),h(),C("fill",n.fill)("stroke-width",n.strokeWidth))},dependencies:[A,ce,xe,O],encapsulation:2,changeDetection:0})}return t})(),vo=(()=>{class t{static \u0275fac=function(i){return new(i||t)};static \u0275mod=j({type:t});static \u0275inj=H({imports:[Si,O,O]})}return t})();var Qt=class t{firestore=S(Lt);auth=S(zt);http=S(wt);get apiBase(){return Rt}authHeaders(){return U(this,null,function*(){let s=this.auth.currentUser;if(!s)throw new Error("Not authenticated");let e=yield s.getIdToken();return new He({Authorization:`Bearer ${e}`})})}getStocks(){return Se(this.authHeaders().then(s=>J(this.http.get(`${this.apiBase}/seasonality/stocks`,{headers:s})))).pipe(Te(s=>s.map(e=>({symbol:e.symbol,displayName:e.display_name,dataUrl:e.data_url,driveFilePresent:e.drive_file_present,driveFileSizeBytes:e.drive_file_size_bytes,driveFileModified:e.drive_file_modified,lastAnalysisAt:e.last_analysis_at,addedAt:e.added_at,addedBy:e.added_by}))))}getCachedResults(s,e,i,n="open"){return Se(this.authHeaders().then(o=>{let r=new qe().set("symbols",s.join(",")).set("view_mode",e).set("years",String(i)).set("return_basis",n);return J(this.http.get(`${this.apiBase}/seasonality/results`,{headers:o,params:r}))})).pipe(Te(o=>o.map(this._mapResult)))}getUpcomingTrades(s,e,i,n,o,r="open",l=0,g="ALL",f){return Se(this.authHeaders().then(d=>J(this.http.post(`${this.apiBase}/seasonality/upcoming-trades`,{symbols:s.length>0?s:null,view_mode:e,years:i==="max"?"max":i,probability_threshold:n,lookahead_days:o,return_basis:r,avg_return_threshold:l,direction_filter:g,min_years_traded:f},{headers:d})))).pipe(Te(d=>d.map(this._mapTrade)))}scanTradesByDate(s,e=60,i=0,n,o="ALL"){return Se(this.authHeaders().then(r=>{let l=new qe().set("date",s).set("probability",String(e)).set("avg_return",String(i)).set("direction",o);return n&&(l=l.set("min_years",n)),J(this.http.get(`${this.apiBase}/seasonality/trade-scanner`,{headers:r,params:l}))})).pipe(Te(r=>r.map(l=>({symbol:l.symbol,displayName:l.displayName||l.display_name,label:l.label,direction:l.direction,posProb:l.posProb??l.pos_prob,negProb:l.negProb??l.neg_prob,avgReturn:l.avgReturn??l.avg_return,sigma:l.sigma,streak:l.streak,count:l.count,yearRange:l.yearRange??l.year_range}))))}addStock(s,e,i){return U(this,null,function*(){let n=yield this.authHeaders();yield J(this.http.post(`${this.apiBase}/seasonality/admin/stocks`,{symbol:s,display_name:e,data_url:i},{headers:n}))})}syncDriveFolder(s){return U(this,null,function*(){let e=yield this.authHeaders(),i=new FormData;s&&i.append("folder_url",s);let n=new He({Authorization:e.get("Authorization")});return yield J(this.http.post(`${this.apiBase}/seasonality/admin/sync-drive-folder`,i,{headers:n}))})}uploadStockFile(s,e,i){return U(this,null,function*(){let n=yield this.authHeaders(),o=new FormData;o.append("symbol",s),e&&o.append("file",e),i&&o.append("data_url",i);let r=new He({Authorization:n.get("Authorization")});yield J(this.http.post(`${this.apiBase}/seasonality/admin/upload`,o,{headers:r}))})}removeStock(s){return U(this,null,function*(){let e=yield this.authHeaders();yield J(this.http.delete(`${this.apiBase}/seasonality/admin/stocks/${s}`,{headers:e}))})}syncNifty500List(){return U(this,null,function*(){let s=yield this.authHeaders();return J(this.http.post(`${this.apiBase}/seasonality/admin/sync-nifty500`,{},{headers:s}))})}triggerAnalysis(s,e,i){return U(this,null,function*(){let n=this.auth.currentUser;if(!n)throw new Error("Not authenticated");let o=yield n.getIdToken(),r=yield fetch(`${this.apiBase}/seasonality/admin/run-analysis/stream`,{method:"POST",headers:{Authorization:`Bearer ${o}`,"Content-Type":"application/json"},body:JSON.stringify({view_modes:s,year_ranges:e})});if(!r.ok){let D=yield r.text();throw new Error(`Analysis failed (HTTP ${r.status}): ${D}`)}let l=r.body.getReader(),g=new TextDecoder,f="",d={done:0,total:0},P=0,k=0;for(;;){let{value:D,done:M}=yield l.read();if(M)break;f+=g.decode(D,{stream:!0});let Y=f.split(`
`);f=Y.pop()??"";for(let c of Y){let u=c.trim();if(u)try{let y=JSON.parse(u);d=y,y.type==="combo"&&(y.status==="ok"?P++:k++),i&&i(y)}catch{}}}return{totalCombos:d.total??0,success:P,errors:k,details:{}}})}getUserConfigs(){let s=this.auth.currentUser;if(!s)return new Ze(n=>n.next([]));let e=Ee(this.firestore,"userSeasonalityConfigs"),i=rt(e,at("uid","==",s.uid),Dt("createdAt","desc"));return ot(i,{idField:"id"})}saveUserConfig(s){return U(this,null,function*(){let e=this.auth.currentUser;if(!e)throw new Error("Not authenticated");let i=Ee(this.firestore,"userSeasonalityConfigs"),n=ze(i);yield lt(n,be(W({},s),{uid:e.uid,createdAt:nt()}))})}deleteUserConfig(s){return U(this,null,function*(){let e=ze(this.firestore,`userSeasonalityConfigs/${s}`);yield st(e)})}getWatchlist(){let s=this.auth.currentUser;if(!s)return new Ze(n=>n.next([]));let e=Ee(this.firestore,"userSeasonalityWatchlist"),i=rt(e,at("uid","==",s.uid));return ot(i,{idField:"id"})}addToWatchlist(s){return U(this,null,function*(){let e=this.auth.currentUser;if(!e)throw new Error("Not authenticated");let i=Ee(this.firestore,"userSeasonalityWatchlist"),n=ze(i);yield lt(n,be(W({},s),{uid:e.uid,addedAt:nt()}))})}removeFromWatchlist(s){return U(this,null,function*(){let e=ze(this.firestore,`userSeasonalityWatchlist/${s}`);yield st(e)})}_mapResult(s){let e=s.grid||{},i=Array.isArray(s.years)?s.years:s.years_list&&Array.isArray(s.years_list)?s.years_list:Object.keys(e);return{id:s.id||"",symbol:s.symbol||"",viewMode:s.viewMode||s.view_mode||"monthly",years:s.years,computedAt:s.computedAt,grid:e,stats:s.stats||{},yearTotals:s.year_totals||s.yearTotals||{},periodsOrdered:s.periods_ordered||s.periodsOrdered||[],years_list:i}}_mapTrade(s){return{symbol:s.symbol,viewMode:s.viewMode||s.view_mode,period:s.period,entryDate:s.entryDate||s.entry_date,exitDate:s.exitDate||s.exit_date,direction:s.direction,posProb:s.posProb??s.pos_prob,negProb:s.negProb??s.neg_prob,avgReturn:s.avgReturn??s.avg_return,sigma:s.sigma,streak:s.streak,daysAway:s.daysAway??s.days_away}}static \u0275fac=function(e){return new(e||t)};static \u0275prov=z({token:t,factory:t.\u0275fac,providedIn:"root"})};var Do=(()=>{class t extends ue{static \u0275fac=(()=>{let e;return function(n){return(e||(e=m(t)))(n||t)}})();static \u0275cmp=x({type:t,selectors:[["BlankIcon"]],features:[v],decls:2,vars:0,consts:[["width","14","height","14","viewBox","0 0 14 14","fill","none","xmlns","http://www.w3.org/2000/svg"],["width","1","height","1","fill","currentColor","fill-opacity","0"]],template:function(i,n){i&1&&(X(),b(0,"svg",0),F(1,"rect",1),w())},encapsulation:2})}return t})();var Bo=(()=>{class t extends ue{static \u0275fac=(()=>{let e;return function(n){return(e||(e=m(t)))(n||t)}})();static \u0275cmp=x({type:t,selectors:[["ChevronDownIcon"]],features:[v],decls:2,vars:5,consts:[["width","14","height","14","viewBox","0 0 14 14","fill","none","xmlns","http://www.w3.org/2000/svg"],["d","M7.01744 10.398C6.91269 10.3985 6.8089 10.378 6.71215 10.3379C6.61541 10.2977 6.52766 10.2386 6.45405 10.1641L1.13907 4.84913C1.03306 4.69404 0.985221 4.5065 1.00399 4.31958C1.02276 4.13266 1.10693 3.95838 1.24166 3.82747C1.37639 3.69655 1.55301 3.61742 1.74039 3.60402C1.92777 3.59062 2.11386 3.64382 2.26584 3.75424L7.01744 8.47394L11.769 3.75424C11.9189 3.65709 12.097 3.61306 12.2748 3.62921C12.4527 3.64535 12.6199 3.72073 12.7498 3.84328C12.8797 3.96582 12.9647 4.12842 12.9912 4.30502C13.0177 4.48162 12.9841 4.662 12.8958 4.81724L7.58083 10.1322C7.50996 10.2125 7.42344 10.2775 7.32656 10.3232C7.22968 10.3689 7.12449 10.3944 7.01744 10.398Z","fill","currentColor"]],template:function(i,n){i&1&&(X(),b(0,"svg",0),F(1,"path",1),w()),i&2&&(E(n.getClassNames()),C("aria-label",n.ariaLabel)("aria-hidden",n.ariaHidden)("role",n.role))},encapsulation:2})}return t})();var Ro=(()=>{class t extends ue{static \u0275fac=(()=>{let e;return function(n){return(e||(e=m(t)))(n||t)}})();static \u0275cmp=x({type:t,selectors:[["ChevronUpIcon"]],features:[v],decls:2,vars:5,consts:[["width","14","height","14","viewBox","0 0 14 14","fill","none","xmlns","http://www.w3.org/2000/svg"],["d","M12.2097 10.4113C12.1057 10.4118 12.0027 10.3915 11.9067 10.3516C11.8107 10.3118 11.7237 10.2532 11.6506 10.1792L6.93602 5.46461L2.22139 10.1476C2.07272 10.244 1.89599 10.2877 1.71953 10.2717C1.54307 10.2556 1.3771 10.1808 1.24822 10.0593C1.11933 9.93766 1.035 9.77633 1.00874 9.6011C0.982477 9.42587 1.0158 9.2469 1.10338 9.09287L6.37701 3.81923C6.52533 3.6711 6.72639 3.58789 6.93602 3.58789C7.14565 3.58789 7.3467 3.6711 7.49502 3.81923L12.7687 9.09287C12.9168 9.24119 13 9.44225 13 9.65187C13 9.8615 12.9168 10.0626 12.7687 10.2109C12.616 10.3487 12.4151 10.4207 12.2097 10.4113Z","fill","currentColor"]],template:function(i,n){i&1&&(X(),b(0,"svg",0),F(1,"path",1),w()),i&2&&(E(n.getClassNames()),C("aria-label",n.ariaLabel)("aria-hidden",n.ariaHidden)("role",n.role))},encapsulation:2})}return t})();var jo=(()=>{class t extends ue{pathId;ngOnInit(){this.pathId="url(#"+kt()+")"}static \u0275fac=(()=>{let e;return function(n){return(e||(e=m(t)))(n||t)}})();static \u0275cmp=x({type:t,selectors:[["SearchIcon"]],features:[v],decls:6,vars:7,consts:[["width","14","height","14","viewBox","0 0 14 14","fill","none","xmlns","http://www.w3.org/2000/svg"],["fill-rule","evenodd","clip-rule","evenodd","d","M2.67602 11.0265C3.6661 11.688 4.83011 12.0411 6.02086 12.0411C6.81149 12.0411 7.59438 11.8854 8.32483 11.5828C8.87005 11.357 9.37808 11.0526 9.83317 10.6803L12.9769 13.8241C13.0323 13.8801 13.0983 13.9245 13.171 13.9548C13.2438 13.985 13.3219 14.0003 13.4007 14C13.4795 14.0003 13.5575 13.985 13.6303 13.9548C13.7031 13.9245 13.7691 13.8801 13.8244 13.8241C13.9367 13.7116 13.9998 13.5592 13.9998 13.4003C13.9998 13.2414 13.9367 13.089 13.8244 12.9765L10.6807 9.8328C11.053 9.37773 11.3573 8.86972 11.5831 8.32452C11.8857 7.59408 12.0414 6.81119 12.0414 6.02056C12.0414 4.8298 11.6883 3.66579 11.0268 2.67572C10.3652 1.68564 9.42494 0.913972 8.32483 0.45829C7.22472 0.00260857 6.01418 -0.116618 4.84631 0.115686C3.67844 0.34799 2.60568 0.921393 1.76369 1.76338C0.921698 2.60537 0.348296 3.67813 0.115991 4.84601C-0.116313 6.01388 0.00291375 7.22441 0.458595 8.32452C0.914277 9.42464 1.68595 10.3649 2.67602 11.0265ZM3.35565 2.0158C4.14456 1.48867 5.07206 1.20731 6.02086 1.20731C7.29317 1.20731 8.51338 1.71274 9.41304 2.6124C10.3127 3.51206 10.8181 4.73226 10.8181 6.00457C10.8181 6.95337 10.5368 7.88088 10.0096 8.66978C9.48251 9.45868 8.73328 10.0736 7.85669 10.4367C6.98011 10.7997 6.01554 10.8947 5.08496 10.7096C4.15439 10.5245 3.2996 10.0676 2.62869 9.39674C1.95778 8.72583 1.50089 7.87104 1.31579 6.94046C1.13068 6.00989 1.22568 5.04532 1.58878 4.16874C1.95187 3.29215 2.56675 2.54292 3.35565 2.0158Z","fill","currentColor"],[3,"id"],["width","14","height","14","fill","white"]],template:function(i,n){i&1&&(X(),b(0,"svg",0)(1,"g"),F(2,"path",1),w(),b(3,"defs")(4,"clipPath",2),F(5,"rect",3),w()()()),i&2&&(E(n.getClassNames()),C("aria-label",n.ariaLabel)("aria-hidden",n.ariaHidden)("role",n.role),h(),C("clip-path",n.pathId),h(3),a("id",n.pathId))},encapsulation:2})}return t})();var Ti=["*"],Ii=({dt:t})=>`
.p-iconfield {
    position: relative;
    display: block;
}

.p-inputicon {
    position: absolute;
    top: 50%;
    margin-top: calc(-1 * (${t("icon.size")} / 2));
    color: ${t("iconfield.icon.color")};
    line-height: 1;
}

.p-iconfield .p-inputicon:first-child {
    inset-inline-start: ${t("form.field.padding.x")};
}

.p-iconfield .p-inputicon:last-child {
    inset-inline-end: ${t("form.field.padding.x")};
}

.p-iconfield .p-inputtext:not(:first-child) {
    padding-inline-start: calc((${t("form.field.padding.x")} * 2) + ${t("icon.size")});
}

.p-iconfield .p-inputtext:not(:last-child) {
    padding-inline-end: calc((${t("form.field.padding.x")} * 2) + ${t("icon.size")});
}

.p-iconfield:has(.p-inputfield-sm) .p-inputicon {
    font-size: ${t("form.field.sm.font.size")};
    width: ${t("form.field.sm.font.size")};
    height: ${t("form.field.sm.font.size")};
    margin-top: calc(-1 * (${t("form.field.sm.font.size")} / 2));
}

.p-iconfield:has(.p-inputfield-lg) .p-inputicon {
    font-size: ${t("form.field.lg.font.size")};
    width: ${t("form.field.lg.font.size")};
    height: ${t("form.field.lg.font.size")};
    margin-top: calc(-1 * (${t("form.field.lg.font.size")} / 2));
}
`,Oi={root:"p-iconfield"},Wt=(()=>{class t extends ${name="iconfield";theme=Ii;classes=Oi;static \u0275fac=(()=>{let e;return function(n){return(e||(e=m(t)))(n||t)}})();static \u0275prov=z({token:t,factory:t.\u0275fac})}return t})();var ts=(()=>{class t extends R{iconPosition="left";get _styleClass(){return this.styleClass}styleClass;_componentStyle=S(Wt);static \u0275fac=(()=>{let e;return function(n){return(e||(e=m(t)))(n||t)}})();static \u0275cmp=x({type:t,selectors:[["p-iconfield"],["p-iconField"],["p-icon-field"]],hostAttrs:[1,"p-iconfield"],hostVars:6,hostBindings:function(i,n){i&2&&(E(n._styleClass),ee("p-iconfield-left",n.iconPosition==="left")("p-iconfield-right",n.iconPosition==="right"))},inputs:{iconPosition:"iconPosition",styleClass:"styleClass"},features:[V([Wt]),v],ngContentSelectors:Ti,decls:1,vars:0,template:function(i,n){i&1&&(le(),ae(0))},dependencies:[A],encapsulation:2,changeDetection:0})}return t})();var ki=["*"],Ei={root:"p-inputicon"},Ut=(()=>{class t extends ${name="inputicon";classes=Ei;static \u0275fac=(()=>{let e;return function(n){return(e||(e=m(t)))(n||t)}})();static \u0275prov=z({token:t,factory:t.\u0275fac})}return t})(),gs=(()=>{class t extends R{styleClass;get hostClasses(){return this.styleClass}_componentStyle=S(Ut);static \u0275fac=(()=>{let e;return function(n){return(e||(e=m(t)))(n||t)}})();static \u0275cmp=x({type:t,selectors:[["p-inputicon"],["p-inputIcon"]],hostVars:4,hostBindings:function(i,n){i&2&&(E(n.hostClasses),ee("p-inputicon",!0))},inputs:{styleClass:"styleClass"},features:[V([Ut]),v],ngContentSelectors:ki,decls:1,vars:0,template:function(i,n){i&1&&(le(),ae(0))},dependencies:[A,O],encapsulation:2,changeDetection:0})}return t})();var zi=({dt:t})=>`
.p-inputtext {
    font-family: inherit;
    font-feature-settings: inherit;
    font-size: 1rem;
    color: ${t("inputtext.color")};
    background: ${t("inputtext.background")};
    padding-block: ${t("inputtext.padding.y")};
    padding-inline: ${t("inputtext.padding.x")};
    border: 1px solid ${t("inputtext.border.color")};
    transition: background ${t("inputtext.transition.duration")}, color ${t("inputtext.transition.duration")}, border-color ${t("inputtext.transition.duration")}, outline-color ${t("inputtext.transition.duration")}, box-shadow ${t("inputtext.transition.duration")};
    appearance: none;
    border-radius: ${t("inputtext.border.radius")};
    outline-color: transparent;
    box-shadow: ${t("inputtext.shadow")};
}

.p-inputtext.ng-invalid.ng-dirty {
    border-color: ${t("inputtext.invalid.border.color")};
}

.p-inputtext:enabled:hover {
    border-color: ${t("inputtext.hover.border.color")};
}

.p-inputtext:enabled:focus {
    border-color: ${t("inputtext.focus.border.color")};
    box-shadow: ${t("inputtext.focus.ring.shadow")};
    outline: ${t("inputtext.focus.ring.width")} ${t("inputtext.focus.ring.style")} ${t("inputtext.focus.ring.color")};
    outline-offset: ${t("inputtext.focus.ring.offset")};
}

.p-inputtext.p-invalid {
    border-color: ${t("inputtext.invalid.border.color")};
}

.p-inputtext.p-variant-filled {
    background: ${t("inputtext.filled.background")};
}
    
.p-inputtext.p-variant-filled:enabled:hover {
    background: ${t("inputtext.filled.hover.background")};
}

.p-inputtext.p-variant-filled:enabled:focus {
    background: ${t("inputtext.filled.focus.background")};
}

.p-inputtext:disabled {
    opacity: 1;
    background: ${t("inputtext.disabled.background")};
    color: ${t("inputtext.disabled.color")};
}

.p-inputtext::placeholder {
    color: ${t("inputtext.placeholder.color")};
}

.p-inputtext.ng-invalid.ng-dirty::placeholder {
    color: ${t("inputtext.invalid.placeholder.color")};
}

.p-inputtext-sm {
    font-size: ${t("inputtext.sm.font.size")};
    padding-block: ${t("inputtext.sm.padding.y")};
    padding-inline: ${t("inputtext.sm.padding.x")};
}

.p-inputtext-lg {
    font-size: ${t("inputtext.lg.font.size")};
    padding-block: ${t("inputtext.lg.padding.y")};
    padding-inline: ${t("inputtext.lg.padding.x")};
}

.p-inputtext-fluid {
    width: 100%;
}
`,Li={root:({instance:t,props:s})=>["p-inputtext p-component",{"p-filled":t.filled,"p-inputtext-sm":s.size==="small","p-inputtext-lg":s.size==="large","p-invalid":s.invalid,"p-variant-filled":s.variant==="filled","p-inputtext-fluid":s.fluid}]},Zt=(()=>{class t extends ${name="inputtext";theme=zi;classes=Li;static \u0275fac=(()=>{let e;return function(n){return(e||(e=m(t)))(n||t)}})();static \u0275prov=z({token:t,factory:t.\u0275fac})}return t})();var Os=(()=>{class t extends R{ngModel;variant;fluid;pSize;filled;_componentStyle=S(Zt);get hasFluid(){let i=this.el.nativeElement.closest("p-fluid");return Ot(this.fluid)?!!i:this.fluid}constructor(e){super(),this.ngModel=e}ngAfterViewInit(){super.ngAfterViewInit(),this.updateFilledState(),this.cd.detectChanges()}ngDoCheck(){this.updateFilledState()}onInput(){this.updateFilledState()}updateFilledState(){this.filled=this.el.nativeElement.value&&this.el.nativeElement.value.length||this.ngModel&&this.ngModel.model}static \u0275fac=function(i){return new(i||t)(me(Qe,8))};static \u0275dir=ut({type:t,selectors:[["","pInputText",""]],hostAttrs:[1,"p-inputtext","p-component"],hostVars:14,hostBindings:function(i,n){if(i&1&&K("input",function(r){return n.onInput(r)}),i&2){let o;ee("p-filled",n.filled)("p-variant-filled",((o=n.variant)!==null&&o!==void 0?o:n.config.inputStyle()||n.config.inputVariant())==="filled")("p-inputtext-fluid",n.hasFluid)("p-inputtext-sm",n.pSize==="small")("p-inputfield-sm",n.pSize==="small")("p-inputtext-lg",n.pSize==="large")("p-inputfield-lg",n.pSize==="large")}},inputs:{variant:"variant",fluid:[2,"fluid","fluid",G],pSize:"pSize"},features:[V([Zt]),v]})}return t})(),ks=(()=>{class t{static \u0275fac=function(i){return new(i||t)};static \u0275mod=j({type:t});static \u0275inj=H({})}return t})();var qt=["content"],Di=["overlay"],Mi=["*"],Fi=(t,s,e,i,n,o,r,l,g,f,d,P,k,D)=>({"p-overlay p-component":!0,"p-overlay-modal p-overlay-mask p-overlay-mask-enter":t,"p-overlay-center":s,"p-overlay-top":e,"p-overlay-top-start":i,"p-overlay-top-end":n,"p-overlay-bottom":o,"p-overlay-bottom-start":r,"p-overlay-bottom-end":l,"p-overlay-left":g,"p-overlay-left-start":f,"p-overlay-left-end":d,"p-overlay-right":P,"p-overlay-right-start":k,"p-overlay-right-end":D}),Bi=(t,s,e)=>({showTransitionParams:t,hideTransitionParams:s,transform:e}),Vi=t=>({value:"visible",params:t}),$i=t=>({mode:t}),Ri=t=>({$implicit:t});function Pi(t,s){t&1&&N(0)}function Ai(t,s){if(t&1){let e=ge();b(0,"div",3,1),K("click",function(n){ie(e);let o=p(2);return ne(o.onOverlayContentClick(n))})("@overlayContentAnimation.start",function(n){ie(e);let o=p(2);return ne(o.onOverlayContentAnimationStart(n))})("@overlayContentAnimation.done",function(n){ie(e);let o=p(2);return ne(o.onOverlayContentAnimationDone(n))}),ae(2),_(3,Pi,1,0,"ng-container",4),w()}if(t&2){let e=p(2);E(e.contentStyleClass),a("ngStyle",e.contentStyle)("ngClass","p-overlay-content")("@overlayContentAnimation",Q(11,Vi,Re(7,Bi,e.showTransitionOptions,e.hideTransitionOptions,e.transformOptions[e.modal?e.overlayResponsiveDirection:"default"]))),h(3),a("ngTemplateOutlet",e.contentTemplate||e._contentTemplate)("ngTemplateOutletContext",Q(15,Ri,Q(13,$i,e.overlayMode)))}}function Hi(t,s){if(t&1){let e=ge();b(0,"div",3,0),K("click",function(){ie(e);let n=p();return ne(n.onOverlayClick())}),_(2,Ai,4,17,"div",2),w()}if(t&2){let e=p();E(e.styleClass),a("ngStyle",e.style)("ngClass",bt(5,Fi,[e.modal,e.modal&&e.overlayResponsiveDirection==="center",e.modal&&e.overlayResponsiveDirection==="top",e.modal&&e.overlayResponsiveDirection==="top-start",e.modal&&e.overlayResponsiveDirection==="top-end",e.modal&&e.overlayResponsiveDirection==="bottom",e.modal&&e.overlayResponsiveDirection==="bottom-start",e.modal&&e.overlayResponsiveDirection==="bottom-end",e.modal&&e.overlayResponsiveDirection==="left",e.modal&&e.overlayResponsiveDirection==="left-start",e.modal&&e.overlayResponsiveDirection==="left-end",e.modal&&e.overlayResponsiveDirection==="right",e.modal&&e.overlayResponsiveDirection==="right-start",e.modal&&e.overlayResponsiveDirection==="right-end"])),h(2),a("ngIf",e.visible)}}var ji=({dt:t})=>`
.p-overlay {
    position: absolute;
    top: 0;
}

.p-overlay-modal {
    display: flex;
    align-items: center;
    justify-content: center;
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
}

.p-overlay-content {
    transform-origin: inherit;
}

.p-overlay-modal > .p-overlay-content {
    z-index: 1;
    width: 90%;
}

/* Position */
/* top */
.p-overlay-top {
    align-items: flex-start;
}
.p-overlay-top-start {
    align-items: flex-start;
    justify-content: flex-start;
}
.p-overlay-top-end {
    align-items: flex-start;
    justify-content: flex-end;
}

/* bottom */
.p-overlay-bottom {
    align-items: flex-end;
}
.p-overlay-bottom-start {
    align-items: flex-end;
    justify-content: flex-start;
}
.p-overlay-bottom-end {
    align-items: flex-end;
    justify-content: flex-end;
}

/* left */
.p-overlay-left {
    justify-content: flex-start;
}
.p-overlay-left-start {
    justify-content: flex-start;
    align-items: flex-start;
}
.p-overlay-left-end {
    justify-content: flex-start;
    align-items: flex-end;
}

/* right */
.p-overlay-right {
    justify-content: flex-end;
}
.p-overlay-right-start {
    justify-content: flex-end;
    align-items: flex-start;
}
.p-overlay-right-end {
    justify-content: flex-end;
    align-items: flex-end;
}
`,Kt=(()=>{class t extends ${name="overlay";theme=ji;static \u0275fac=(()=>{let e;return function(n){return(e||(e=m(t)))(n||t)}})();static \u0275prov=z({token:t,factory:t.\u0275fac})}return t})(),Ni=Je([Ge({transform:"{{transform}}",opacity:0}),Ke("{{showTransitionParams}}")]),Qi=Je([Ke("{{hideTransitionParams}}",Ge({transform:"{{transform}}",opacity:0}))]),Wi=(()=>{class t extends R{overlayService;zone;get visible(){return this._visible}set visible(e){this._visible=e,this._visible&&!this.modalVisible&&(this.modalVisible=!0)}get mode(){return this._mode||this.overlayOptions?.mode}set mode(e){this._mode=e}get style(){return De.merge(this._style,this.modal?this.overlayResponsiveOptions?.style:this.overlayOptions?.style)}set style(e){this._style=e}get styleClass(){return De.merge(this._styleClass,this.modal?this.overlayResponsiveOptions?.styleClass:this.overlayOptions?.styleClass)}set styleClass(e){this._styleClass=e}get contentStyle(){return De.merge(this._contentStyle,this.modal?this.overlayResponsiveOptions?.contentStyle:this.overlayOptions?.contentStyle)}set contentStyle(e){this._contentStyle=e}get contentStyleClass(){return De.merge(this._contentStyleClass,this.modal?this.overlayResponsiveOptions?.contentStyleClass:this.overlayOptions?.contentStyleClass)}set contentStyleClass(e){this._contentStyleClass=e}get target(){let e=this._target||this.overlayOptions?.target;return e===void 0?"@prev":e}set target(e){this._target=e}get appendTo(){return this._appendTo||this.overlayOptions?.appendTo}set appendTo(e){this._appendTo=e}get autoZIndex(){let e=this._autoZIndex||this.overlayOptions?.autoZIndex;return e===void 0?!0:e}set autoZIndex(e){this._autoZIndex=e}get baseZIndex(){let e=this._baseZIndex||this.overlayOptions?.baseZIndex;return e===void 0?0:e}set baseZIndex(e){this._baseZIndex=e}get showTransitionOptions(){let e=this._showTransitionOptions||this.overlayOptions?.showTransitionOptions;return e===void 0?".12s cubic-bezier(0, 0, 0.2, 1)":e}set showTransitionOptions(e){this._showTransitionOptions=e}get hideTransitionOptions(){let e=this._hideTransitionOptions||this.overlayOptions?.hideTransitionOptions;return e===void 0?".1s linear":e}set hideTransitionOptions(e){this._hideTransitionOptions=e}get listener(){return this._listener||this.overlayOptions?.listener}set listener(e){this._listener=e}get responsive(){return this._responsive||this.overlayOptions?.responsive}set responsive(e){this._responsive=e}get options(){return this._options}set options(e){this._options=e}visibleChange=new L;onBeforeShow=new L;onShow=new L;onBeforeHide=new L;onHide=new L;onAnimationStart=new L;onAnimationDone=new L;overlayViewChild;contentViewChild;contentTemplate;templates;_contentTemplate;_visible=!1;_mode;_style;_styleClass;_contentStyle;_contentStyleClass;_target;_appendTo;_autoZIndex;_baseZIndex;_showTransitionOptions;_hideTransitionOptions;_listener;_responsive;_options;modalVisible=!1;isOverlayClicked=!1;isOverlayContentClicked=!1;scrollHandler;documentClickListener;documentResizeListener;_componentStyle=S(Kt);documentKeyboardListener;window;transformOptions={default:"scaleY(0.8)",center:"scale(0.7)",top:"translate3d(0px, -100%, 0px)","top-start":"translate3d(0px, -100%, 0px)","top-end":"translate3d(0px, -100%, 0px)",bottom:"translate3d(0px, 100%, 0px)","bottom-start":"translate3d(0px, 100%, 0px)","bottom-end":"translate3d(0px, 100%, 0px)",left:"translate3d(-100%, 0px, 0px)","left-start":"translate3d(-100%, 0px, 0px)","left-end":"translate3d(-100%, 0px, 0px)",right:"translate3d(100%, 0px, 0px)","right-start":"translate3d(100%, 0px, 0px)","right-end":"translate3d(100%, 0px, 0px)"};get modal(){if(Oe(this.platformId))return this.mode==="modal"||this.overlayResponsiveOptions&&this.document.defaultView?.matchMedia(this.overlayResponsiveOptions.media?.replace("@media","")||`(max-width: ${this.overlayResponsiveOptions.breakpoint})`).matches}get overlayMode(){return this.mode||(this.modal?"modal":"overlay")}get overlayOptions(){return W(W({},this.config?.overlayOptions),this.options)}get overlayResponsiveOptions(){return W(W({},this.overlayOptions?.responsive),this.responsive)}get overlayResponsiveDirection(){return this.overlayResponsiveOptions?.direction||"center"}get overlayEl(){return this.overlayViewChild?.nativeElement}get contentEl(){return this.contentViewChild?.nativeElement}get targetEl(){return It(this.target,this.el?.nativeElement)}constructor(e,i){super(),this.overlayService=e,this.zone=i}ngAfterContentInit(){this.templates?.forEach(e=>{switch(e.getType()){case"content":this._contentTemplate=e.template;break;default:this._contentTemplate=e.template;break}})}show(e,i=!1){this.onVisibleChange(!0),this.handleEvents("onShow",{overlay:e||this.overlayEl,target:this.targetEl,mode:this.overlayMode}),i&&tt(this.targetEl),this.modal&&et(this.document?.body,"p-overflow-hidden")}hide(e,i=!1){if(this.visible)this.onVisibleChange(!1),this.handleEvents("onHide",{overlay:e||this.overlayEl,target:this.targetEl,mode:this.overlayMode}),i&&tt(this.targetEl),this.modal&&St(this.document?.body,"p-overflow-hidden");else return}alignOverlay(){!this.modal&&Le.alignOverlay(this.overlayEl,this.targetEl,this.appendTo)}onVisibleChange(e){this._visible=e,this.visibleChange.emit(e)}onOverlayClick(){this.isOverlayClicked=!0}onOverlayContentClick(e){this.overlayService.add({originalEvent:e,target:this.targetEl}),this.isOverlayContentClicked=!0}onOverlayContentAnimationStart(e){switch(e.toState){case"visible":this.handleEvents("onBeforeShow",{overlay:this.overlayEl,target:this.targetEl,mode:this.overlayMode}),this.autoZIndex&&We.set(this.overlayMode,this.overlayEl,this.baseZIndex+this.config?.zIndex[this.overlayMode]),Le.appendOverlay(this.overlayEl,this.appendTo==="body"?this.document.body:this.appendTo,this.appendTo),this.alignOverlay();break;case"void":this.handleEvents("onBeforeHide",{overlay:this.overlayEl,target:this.targetEl,mode:this.overlayMode}),this.modal&&et(this.overlayEl,"p-overlay-mask-leave");break}this.handleEvents("onAnimationStart",e)}onOverlayContentAnimationDone(e){let i=this.overlayEl||e.element.parentElement;switch(e.toState){case"visible":this.visible&&(this.show(i,!0),this.bindListeners());break;case"void":if(!this.visible){this.hide(i,!0),this.modalVisible=!1,this.unbindListeners(),Le.appendOverlay(this.overlayEl,this.targetEl,this.appendTo),We.clear(i),this.cd.markForCheck();break}}this.handleEvents("onAnimationDone",e)}handleEvents(e,i){this[e].emit(i),this.options&&this.options[e]&&this.options[e](i),this.config?.overlayOptions&&(this.config?.overlayOptions)[e]&&(this.config?.overlayOptions)[e](i)}bindListeners(){this.bindScrollListener(),this.bindDocumentClickListener(),this.bindDocumentResizeListener(),this.bindDocumentKeyboardListener()}unbindListeners(){this.unbindScrollListener(),this.unbindDocumentClickListener(),this.unbindDocumentResizeListener(),this.unbindDocumentKeyboardListener()}bindScrollListener(){this.scrollHandler||(this.scrollHandler=new Bt(this.targetEl,e=>{(this.listener?this.listener(e,{type:"scroll",mode:this.overlayMode,valid:!0}):!0)&&this.hide(e,!0)})),this.scrollHandler.bindScrollListener()}unbindScrollListener(){this.scrollHandler&&this.scrollHandler.unbindScrollListener()}bindDocumentClickListener(){this.documentClickListener||(this.documentClickListener=this.renderer.listen(this.document,"click",e=>{let n=!(this.targetEl&&(this.targetEl.isSameNode(e.target)||!this.isOverlayClicked&&this.targetEl.contains(e.target)))&&!this.isOverlayContentClicked;(this.listener?this.listener(e,{type:"outside",mode:this.overlayMode,valid:e.which!==3&&n}):n)&&this.hide(e),this.isOverlayClicked=this.isOverlayContentClicked=!1}))}unbindDocumentClickListener(){this.documentClickListener&&(this.documentClickListener(),this.documentClickListener=null)}bindDocumentResizeListener(){this.documentResizeListener||(this.documentResizeListener=this.renderer.listen(this.document.defaultView,"resize",e=>{(this.listener?this.listener(e,{type:"resize",mode:this.overlayMode,valid:!ve()}):!ve())&&this.hide(e,!0)}))}unbindDocumentResizeListener(){this.documentResizeListener&&(this.documentResizeListener(),this.documentResizeListener=null)}bindDocumentKeyboardListener(){this.documentKeyboardListener||this.zone.runOutsideAngular(()=>{this.documentKeyboardListener=this.renderer.listen(this.document.defaultView,"keydown",e=>{if(this.overlayOptions.hideOnEscape===!1||e.code!=="Escape")return;(this.listener?this.listener(e,{type:"keydown",mode:this.overlayMode,valid:!ve()}):!ve())&&this.zone.run(()=>{this.hide(e,!0)})})})}unbindDocumentKeyboardListener(){this.documentKeyboardListener&&(this.documentKeyboardListener(),this.documentKeyboardListener=null)}ngOnDestroy(){this.hide(this.overlayEl,!0),this.overlayEl&&(Le.appendOverlay(this.overlayEl,this.targetEl,this.appendTo),We.clear(this.overlayEl)),this.scrollHandler&&(this.scrollHandler.destroy(),this.scrollHandler=null),this.unbindListeners(),super.ngOnDestroy()}static \u0275fac=function(i){return new(i||t)(me(Et),me(Be))};static \u0275cmp=x({type:t,selectors:[["p-overlay"]],contentQueries:function(i,n,o){if(i&1&&(B(o,qt,4),B(o,pe,4)),i&2){let r;T(r=I())&&(n.contentTemplate=r.first),T(r=I())&&(n.templates=r)}},viewQuery:function(i,n){if(i&1&&(we(Di,5),we(qt,5)),i&2){let o;T(o=I())&&(n.overlayViewChild=o.first),T(o=I())&&(n.contentViewChild=o.first)}},inputs:{visible:"visible",mode:"mode",style:"style",styleClass:"styleClass",contentStyle:"contentStyle",contentStyleClass:"contentStyleClass",target:"target",appendTo:"appendTo",autoZIndex:"autoZIndex",baseZIndex:"baseZIndex",showTransitionOptions:"showTransitionOptions",hideTransitionOptions:"hideTransitionOptions",listener:"listener",responsive:"responsive",options:"options"},outputs:{visibleChange:"visibleChange",onBeforeShow:"onBeforeShow",onShow:"onShow",onBeforeHide:"onBeforeHide",onHide:"onHide",onAnimationStart:"onAnimationStart",onAnimationDone:"onAnimationDone"},features:[V([Kt]),v],ngContentSelectors:Mi,decls:1,vars:1,consts:[["overlay",""],["content",""],[3,"ngStyle","class","ngClass","click",4,"ngIf"],[3,"click","ngStyle","ngClass"],[4,"ngTemplateOutlet","ngTemplateOutletContext"]],template:function(i,n){i&1&&(le(),_(0,Hi,3,20,"div",2)),i&2&&a("ngIf",n.modalVisible)},dependencies:[A,ce,Ae,de,xe,O],encapsulation:2,data:{animation:[xt("overlayContentAnimation",[Ye(":enter",[Xe(Ni)]),Ye(":leave",[Xe(Qi)])])]},changeDetection:0})}return t})(),Gs=(()=>{class t{static \u0275fac=function(i){return new(i||t)};static \u0275mod=j({type:t});static \u0275inj=H({imports:[Wi,O,O]})}return t})();var Gt=["content"],Ui=["item"],Zi=["loader"],qi=["loadericon"],Ki=["element"],Gi=["*"],Yi=(t,s,e)=>({"p-virtualscroller":!0,"p-virtualscroller-inline":t,"p-virtualscroller-both p-both-scroll":s,"p-virtualscroller-horizontal p-horizontal-scroll":e}),dt=(t,s)=>({$implicit:t,options:s}),Ji=t=>({"p-virtualscroller-content":!0,"p-virtualscroller-loading ":t}),Xi=t=>({"p-virtualscroller-loader-mask":t}),en=t=>({numCols:t}),Jt=t=>({options:t}),tn=()=>({styleClass:"p-virtualscroller-loading-icon"}),nn=(t,s)=>({rows:t,columns:s});function on(t,s){t&1&&N(0)}function sn(t,s){if(t&1&&(se(0),_(1,on,1,0,"ng-container",10),re()),t&2){let e=p(2);h(),a("ngTemplateOutlet",e.contentTemplate||e._contentTemplate)("ngTemplateOutletContext",oe(2,dt,e.loadedItems,e.getContentOptions()))}}function rn(t,s){t&1&&N(0)}function ln(t,s){if(t&1&&(se(0),_(1,rn,1,0,"ng-container",10),re()),t&2){let e=s.$implicit,i=s.index,n=p(3);h(),a("ngTemplateOutlet",n.itemTemplate||n._itemTemplate)("ngTemplateOutletContext",oe(2,dt,e,n.getOptions(i)))}}function an(t,s){if(t&1&&(b(0,"div",11,3),_(2,ln,2,5,"ng-container",12),w()),t&2){let e=p(2);$e(e.contentStyle),E(e.contentStyleClass),a("ngClass",Q(8,Ji,e.d_loading)),C("data-pc-section","content"),h(2),a("ngForOf",e.loadedItems)("ngForTrackBy",e._trackBy)}}function cn(t,s){if(t&1&&F(0,"div",13),t&2){let e=p(2);a("ngStyle",e.spacerStyle),C("data-pc-section","spacer")}}function dn(t,s){t&1&&N(0)}function pn(t,s){if(t&1&&(se(0),_(1,dn,1,0,"ng-container",10),re()),t&2){let e=s.index,i=p(4);h(),a("ngTemplateOutlet",i.loaderTemplate||i._loaderTemplate)("ngTemplateOutletContext",Q(4,Jt,i.getLoaderOptions(e,i.both&&Q(2,en,i.numItemsInViewport.cols))))}}function un(t,s){if(t&1&&(se(0),_(1,pn,2,6,"ng-container",15),re()),t&2){let e=p(3);h(),a("ngForOf",e.loaderArr)}}function hn(t,s){t&1&&N(0)}function mn(t,s){if(t&1&&(se(0),_(1,hn,1,0,"ng-container",10),re()),t&2){let e=p(4);h(),a("ngTemplateOutlet",e.loaderIconTemplate||e._loaderIconTemplate)("ngTemplateOutletContext",Q(3,Jt,vt(2,tn)))}}function gn(t,s){t&1&&F(0,"SpinnerIcon",16),t&2&&(a("styleClass","p-virtualscroller-loading-icon pi-spin"),C("data-pc-section","loadingIcon"))}function fn(t,s){if(t&1&&_(0,mn,2,5,"ng-container",6)(1,gn,1,2,"ng-template",null,5,fe),t&2){let e=Ie(2),i=p(3);a("ngIf",i.loaderIconTemplate||i._loaderIconTemplate)("ngIfElse",e)}}function yn(t,s){if(t&1&&(b(0,"div",14),_(1,un,2,1,"ng-container",6)(2,fn,3,2,"ng-template",null,4,fe),w()),t&2){let e=Ie(3),i=p(2);a("ngClass",Q(4,Xi,!i.loaderTemplate)),C("data-pc-section","loader"),h(),a("ngIf",i.loaderTemplate||i._loaderTemplate)("ngIfElse",e)}}function _n(t,s){if(t&1){let e=ge();se(0),b(1,"div",7,1),K("scroll",function(n){ie(e);let o=p();return ne(o.onContainerScroll(n))}),_(3,sn,2,5,"ng-container",6)(4,an,3,10,"ng-template",null,2,fe)(6,cn,1,2,"div",8)(7,yn,4,6,"div",9),w(),re()}if(t&2){let e=Ie(5),i=p();h(),E(i._styleClass),a("ngStyle",i._style)("ngClass",Re(12,Yi,i.inline,i.both,i.horizontal)),C("id",i._id)("tabindex",i.tabindex)("data-pc-name","scroller")("data-pc-section","root"),h(2),a("ngIf",i.contentTemplate||i._contentTemplate)("ngIfElse",e),h(3),a("ngIf",i._showSpacer),h(),a("ngIf",!i.loaderDisabled&&i._showLoader&&i.d_loading)}}function vn(t,s){t&1&&N(0)}function bn(t,s){if(t&1&&(se(0),_(1,vn,1,0,"ng-container",10),re()),t&2){let e=p(2);h(),a("ngTemplateOutlet",e.contentTemplate||e._contentTemplate)("ngTemplateOutletContext",oe(5,dt,e.items,oe(2,nn,e._items,e.loadedColumns)))}}function Cn(t,s){if(t&1&&(ae(0),_(1,bn,2,8,"ng-container",17)),t&2){let e=p();h(),a("ngIf",e.contentTemplate||e._contentTemplate)}}var wn=({dt:t})=>`
.p-virtualscroller {
    position: relative;
    overflow: auto;
    contain: strict;
    transform: translateZ(0);
    will-change: scroll-position;
    outline: 0 none;
}

.p-virtualscroller-content {
    position: absolute;
    top: 0;
    left: 0;
    min-height: 100%;
    min-width: 100%;
    will-change: transform;
}

.p-virtualscroller-spacer {
    position: absolute;
    top: 0;
    left: 0;
    height: 1px;
    width: 1px;
    transform-origin: 0 0;
    pointer-events: none;
}

.p-virtualscroller-loader {
    position: sticky;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: ${t("virtualscroller.loader.mask.background")};
    color: ${t("virtualscroller.loader.mask.color")};
}

.p-virtualscroller-loader-mask {
    display: flex;
    align-items: center;
    justify-content: center;
}

.p-virtualscroller-loading-icon {
    font-size: ${t("virtualscroller.loader.icon.size")};
    width: ${t("virtualscroller.loader.icon.size")};
    height: ${t("virtualscroller.loader.icon.size")};
}

.p-virtualscroller-horizontal > .p-virtualscroller-content {
    display: flex;
}

.p-virtualscroller-inline .p-virtualscroller-content {
    position: static;
}
`,Yt=(()=>{class t extends ${name="virtualscroller";theme=wn;static \u0275fac=(()=>{let e;return function(n){return(e||(e=m(t)))(n||t)}})();static \u0275prov=z({token:t,factory:t.\u0275fac})}return t})();var xn=(()=>{class t extends R{zone;get id(){return this._id}set id(e){this._id=e}get style(){return this._style}set style(e){this._style=e}get styleClass(){return this._styleClass}set styleClass(e){this._styleClass=e}get tabindex(){return this._tabindex}set tabindex(e){this._tabindex=e}get items(){return this._items}set items(e){this._items=e}get itemSize(){return this._itemSize}set itemSize(e){this._itemSize=e}get scrollHeight(){return this._scrollHeight}set scrollHeight(e){this._scrollHeight=e}get scrollWidth(){return this._scrollWidth}set scrollWidth(e){this._scrollWidth=e}get orientation(){return this._orientation}set orientation(e){this._orientation=e}get step(){return this._step}set step(e){this._step=e}get delay(){return this._delay}set delay(e){this._delay=e}get resizeDelay(){return this._resizeDelay}set resizeDelay(e){this._resizeDelay=e}get appendOnly(){return this._appendOnly}set appendOnly(e){this._appendOnly=e}get inline(){return this._inline}set inline(e){this._inline=e}get lazy(){return this._lazy}set lazy(e){this._lazy=e}get disabled(){return this._disabled}set disabled(e){this._disabled=e}get loaderDisabled(){return this._loaderDisabled}set loaderDisabled(e){this._loaderDisabled=e}get columns(){return this._columns}set columns(e){this._columns=e}get showSpacer(){return this._showSpacer}set showSpacer(e){this._showSpacer=e}get showLoader(){return this._showLoader}set showLoader(e){this._showLoader=e}get numToleratedItems(){return this._numToleratedItems}set numToleratedItems(e){this._numToleratedItems=e}get loading(){return this._loading}set loading(e){this._loading=e}get autoSize(){return this._autoSize}set autoSize(e){this._autoSize=e}get trackBy(){return this._trackBy}set trackBy(e){this._trackBy=e}get options(){return this._options}set options(e){this._options=e,e&&typeof e=="object"&&(Object.entries(e).forEach(([i,n])=>this[`_${i}`]!==n&&(this[`_${i}`]=n)),Object.entries(e).forEach(([i,n])=>this[`${i}`]!==n&&(this[`${i}`]=n)))}onLazyLoad=new L;onScroll=new L;onScrollIndexChange=new L;elementViewChild;contentViewChild;height;_id;_style;_styleClass;_tabindex=0;_items;_itemSize=0;_scrollHeight;_scrollWidth;_orientation="vertical";_step=0;_delay=0;_resizeDelay=10;_appendOnly=!1;_inline=!1;_lazy=!1;_disabled=!1;_loaderDisabled=!1;_columns;_showSpacer=!0;_showLoader=!1;_numToleratedItems;_loading;_autoSize=!1;_trackBy;_options;d_loading=!1;d_numToleratedItems;contentEl;contentTemplate;itemTemplate;loaderTemplate;loaderIconTemplate;templates;_contentTemplate;_itemTemplate;_loaderTemplate;_loaderIconTemplate;first=0;last=0;page=0;isRangeChanged=!1;numItemsInViewport=0;lastScrollPos=0;lazyLoadState={};loaderArr=[];spacerStyle={};contentStyle={};scrollTimeout;resizeTimeout;initialized=!1;windowResizeListener;defaultWidth;defaultHeight;defaultContentWidth;defaultContentHeight;_contentStyleClass;get contentStyleClass(){return this._contentStyleClass}set contentStyleClass(e){this._contentStyleClass=e}get vertical(){return this._orientation==="vertical"}get horizontal(){return this._orientation==="horizontal"}get both(){return this._orientation==="both"}get loadedItems(){return this._items&&!this.d_loading?this.both?this._items.slice(this._appendOnly?0:this.first.rows,this.last.rows).map(e=>this._columns?e:e.slice(this._appendOnly?0:this.first.cols,this.last.cols)):this.horizontal&&this._columns?this._items:this._items.slice(this._appendOnly?0:this.first,this.last):[]}get loadedRows(){return this.d_loading?this._loaderDisabled?this.loaderArr:[]:this.loadedItems}get loadedColumns(){return this._columns&&(this.both||this.horizontal)?this.d_loading&&this._loaderDisabled?this.both?this.loaderArr[0]:this.loaderArr:this._columns.slice(this.both?this.first.cols:this.first,this.both?this.last.cols:this.last):this._columns}_componentStyle=S(Yt);constructor(e){super(),this.zone=e}ngOnInit(){super.ngOnInit(),this.setInitialState()}ngOnChanges(e){super.ngOnChanges(e);let i=!1;if(this.scrollHeight=="100%"&&(this.height="100%"),e.loading){let{previousValue:n,currentValue:o}=e.loading;this.lazy&&n!==o&&o!==this.d_loading&&(this.d_loading=o,i=!0)}if(e.orientation&&(this.lastScrollPos=this.both?{top:0,left:0}:0),e.numToleratedItems){let{previousValue:n,currentValue:o}=e.numToleratedItems;n!==o&&o!==this.d_numToleratedItems&&(this.d_numToleratedItems=o)}if(e.options){let{previousValue:n,currentValue:o}=e.options;this.lazy&&n?.loading!==o?.loading&&o?.loading!==this.d_loading&&(this.d_loading=o.loading,i=!0),n?.numToleratedItems!==o?.numToleratedItems&&o?.numToleratedItems!==this.d_numToleratedItems&&(this.d_numToleratedItems=o.numToleratedItems)}this.initialized&&!i&&(e.items?.previousValue?.length!==e.items?.currentValue?.length||e.itemSize||e.scrollHeight||e.scrollWidth)&&(this.init(),this.calculateAutoSize())}ngAfterContentInit(){this.templates.forEach(e=>{switch(e.getType()){case"content":this._contentTemplate=e.template;break;case"item":this._itemTemplate=e.template;break;case"loader":this._loaderTemplate=e.template;break;case"loadericon":this._loaderIconTemplate=e.template;break;default:this._itemTemplate=e.template;break}})}ngAfterViewInit(){super.ngAfterViewInit(),Promise.resolve().then(()=>{this.viewInit()})}ngAfterViewChecked(){this.initialized||this.viewInit()}ngOnDestroy(){this.unbindResizeListener(),this.contentEl=null,this.initialized=!1,super.ngOnDestroy()}viewInit(){Oe(this.platformId)&&!this.initialized&&it(this.elementViewChild?.nativeElement)&&(this.setInitialState(),this.setContentEl(this.contentEl),this.init(),this.defaultWidth=_e(this.elementViewChild?.nativeElement),this.defaultHeight=ye(this.elementViewChild?.nativeElement),this.defaultContentWidth=_e(this.contentEl),this.defaultContentHeight=ye(this.contentEl),this.initialized=!0)}init(){this._disabled||(this.setSize(),this.calculateOptions(),this.setSpacerSize(),this.bindResizeListener(),this.cd.detectChanges())}setContentEl(e){this.contentEl=e||this.contentViewChild?.nativeElement||Tt(this.elementViewChild?.nativeElement,".p-virtualscroller-content")}setInitialState(){this.first=this.both?{rows:0,cols:0}:0,this.last=this.both?{rows:0,cols:0}:0,this.numItemsInViewport=this.both?{rows:0,cols:0}:0,this.lastScrollPos=this.both?{top:0,left:0}:0,this.d_loading=this._loading||!1,this.d_numToleratedItems=this._numToleratedItems,this.loaderArr=[]}getElementRef(){return this.elementViewChild}getPageByFirst(e){return Math.floor(((e??this.first)+this.d_numToleratedItems*4)/(this._step||1))}isPageChanged(e){return this._step?this.page!==this.getPageByFirst(e??this.first):!0}scrollTo(e){this.elementViewChild?.nativeElement?.scrollTo(e)}scrollToIndex(e,i="auto"){if(this.both?e.every(o=>o>-1):e>-1){let o=this.first,{scrollTop:r=0,scrollLeft:l=0}=this.elementViewChild?.nativeElement,{numToleratedItems:g}=this.calculateNumItems(),f=this.getContentPosition(),d=this.itemSize,P=(u=0,y)=>u<=y?0:u,k=(u,y,q)=>u*y+q,D=(u=0,y=0)=>this.scrollTo({left:u,top:y,behavior:i}),M=this.both?{rows:0,cols:0}:0,Y=!1,c=!1;this.both?(M={rows:P(e[0],g[0]),cols:P(e[1],g[1])},D(k(M.cols,d[1],f.left),k(M.rows,d[0],f.top)),c=this.lastScrollPos.top!==r||this.lastScrollPos.left!==l,Y=M.rows!==o.rows||M.cols!==o.cols):(M=P(e,g),this.horizontal?D(k(M,d,f.left),r):D(l,k(M,d,f.top)),c=this.lastScrollPos!==(this.horizontal?l:r),Y=M!==o),this.isRangeChanged=Y,c&&(this.first=M)}}scrollInView(e,i,n="auto"){if(i){let{first:o,viewport:r}=this.getRenderedRange(),l=(d=0,P=0)=>this.scrollTo({left:d,top:P,behavior:n}),g=i==="to-start",f=i==="to-end";if(g){if(this.both)r.first.rows-o.rows>e[0]?l(r.first.cols*this._itemSize[1],(r.first.rows-1)*this._itemSize[0]):r.first.cols-o.cols>e[1]&&l((r.first.cols-1)*this._itemSize[1],r.first.rows*this._itemSize[0]);else if(r.first-o>e){let d=(r.first-1)*this._itemSize;this.horizontal?l(d,0):l(0,d)}}else if(f){if(this.both)r.last.rows-o.rows<=e[0]+1?l(r.first.cols*this._itemSize[1],(r.first.rows+1)*this._itemSize[0]):r.last.cols-o.cols<=e[1]+1&&l((r.first.cols+1)*this._itemSize[1],r.first.rows*this._itemSize[0]);else if(r.last-o<=e+1){let d=(r.first+1)*this._itemSize;this.horizontal?l(d,0):l(0,d)}}}else this.scrollToIndex(e,n)}getRenderedRange(){let e=(o,r)=>r||o?Math.floor(o/(r||o)):0,i=this.first,n=0;if(this.elementViewChild?.nativeElement){let{scrollTop:o,scrollLeft:r}=this.elementViewChild.nativeElement;if(this.both)i={rows:e(o,this._itemSize[0]),cols:e(r,this._itemSize[1])},n={rows:i.rows+this.numItemsInViewport.rows,cols:i.cols+this.numItemsInViewport.cols};else{let l=this.horizontal?r:o;i=e(l,this._itemSize),n=i+this.numItemsInViewport}}return{first:this.first,last:this.last,viewport:{first:i,last:n}}}calculateNumItems(){let e=this.getContentPosition(),i=(this.elementViewChild?.nativeElement?this.elementViewChild.nativeElement.offsetWidth-e.left:0)||0,n=(this.elementViewChild?.nativeElement?this.elementViewChild.nativeElement.offsetHeight-e.top:0)||0,o=(f,d)=>d||f?Math.ceil(f/(d||f)):0,r=f=>Math.ceil(f/2),l=this.both?{rows:o(n,this._itemSize[0]),cols:o(i,this._itemSize[1])}:o(this.horizontal?i:n,this._itemSize),g=this.d_numToleratedItems||(this.both?[r(l.rows),r(l.cols)]:r(l));return{numItemsInViewport:l,numToleratedItems:g}}calculateOptions(){let{numItemsInViewport:e,numToleratedItems:i}=this.calculateNumItems(),n=(l,g,f,d=!1)=>this.getLast(l+g+(l<f?2:3)*f,d),o=this.first,r=this.both?{rows:n(this.first.rows,e.rows,i[0]),cols:n(this.first.cols,e.cols,i[1],!0)}:n(this.first,e,i);this.last=r,this.numItemsInViewport=e,this.d_numToleratedItems=i,this.showLoader&&(this.loaderArr=this.both?Array.from({length:e.rows}).map(()=>Array.from({length:e.cols})):Array.from({length:e})),this._lazy&&Promise.resolve().then(()=>{this.lazyLoadState={first:this._step?this.both?{rows:0,cols:o.cols}:0:o,last:Math.min(this._step?this._step:this.last,this.items.length)},this.handleEvents("onLazyLoad",this.lazyLoadState)})}calculateAutoSize(){this._autoSize&&!this.d_loading&&Promise.resolve().then(()=>{if(this.contentEl){this.contentEl.style.minHeight=this.contentEl.style.minWidth="auto",this.contentEl.style.position="relative",this.elementViewChild.nativeElement.style.contain="none";let[e,i]=[_e(this.contentEl),ye(this.contentEl)];e!==this.defaultContentWidth&&(this.elementViewChild.nativeElement.style.width=""),i!==this.defaultContentHeight&&(this.elementViewChild.nativeElement.style.height="");let[n,o]=[_e(this.elementViewChild.nativeElement),ye(this.elementViewChild.nativeElement)];(this.both||this.horizontal)&&(this.elementViewChild.nativeElement.style.width=n<this.defaultWidth?n+"px":this._scrollWidth||this.defaultWidth+"px"),(this.both||this.vertical)&&(this.elementViewChild.nativeElement.style.height=o<this.defaultHeight?o+"px":this._scrollHeight||this.defaultHeight+"px"),this.contentEl.style.minHeight=this.contentEl.style.minWidth="",this.contentEl.style.position="",this.elementViewChild.nativeElement.style.contain=""}})}getLast(e=0,i=!1){return this._items?Math.min(i?(this._columns||this._items[0]).length:this._items.length,e):0}getContentPosition(){if(this.contentEl){let e=getComputedStyle(this.contentEl),i=parseFloat(e.paddingLeft)+Math.max(parseFloat(e.left)||0,0),n=parseFloat(e.paddingRight)+Math.max(parseFloat(e.right)||0,0),o=parseFloat(e.paddingTop)+Math.max(parseFloat(e.top)||0,0),r=parseFloat(e.paddingBottom)+Math.max(parseFloat(e.bottom)||0,0);return{left:i,right:n,top:o,bottom:r,x:i+n,y:o+r}}return{left:0,right:0,top:0,bottom:0,x:0,y:0}}setSize(){if(this.elementViewChild?.nativeElement){let e=this.elementViewChild.nativeElement.parentElement.parentElement,i=this._scrollWidth||`${this.elementViewChild.nativeElement.offsetWidth||e.offsetWidth}px`,n=this._scrollHeight||`${this.elementViewChild.nativeElement.offsetHeight||e.offsetHeight}px`,o=(r,l)=>this.elementViewChild.nativeElement.style[r]=l;this.both||this.horizontal?(o("height",n),o("width",i)):o("height",n)}}setSpacerSize(){if(this._items){let e=this.getContentPosition(),i=(n,o,r,l=0)=>this.spacerStyle=be(W({},this.spacerStyle),{[`${n}`]:(o||[]).length*r+l+"px"});this.both?(i("height",this._items,this._itemSize[0],e.y),i("width",this._columns||this._items[1],this._itemSize[1],e.x)):this.horizontal?i("width",this._columns||this._items,this._itemSize,e.x):i("height",this._items,this._itemSize,e.y)}}setContentPosition(e){if(this.contentEl&&!this._appendOnly){let i=e?e.first:this.first,n=(r,l)=>r*l,o=(r=0,l=0)=>this.contentStyle=be(W({},this.contentStyle),{transform:`translate3d(${r}px, ${l}px, 0)`});if(this.both)o(n(i.cols,this._itemSize[1]),n(i.rows,this._itemSize[0]));else{let r=n(i,this._itemSize);this.horizontal?o(r,0):o(0,r)}}}onScrollPositionChange(e){let i=e.target,n=this.getContentPosition(),o=(c,u)=>c?c>u?c-u:c:0,r=(c,u)=>u||c?Math.floor(c/(u||c)):0,l=(c,u,y,q,te,he)=>c<=te?te:he?y-q-te:u+te-1,g=(c,u,y,q,te,he,Me)=>c<=he?0:Math.max(0,Me?c<u?y:c-he:c>u?y:c-2*he),f=(c,u,y,q,te,he=!1)=>{let Me=u+q+2*te;return c>=te&&(Me+=te+1),this.getLast(Me,he)},d=o(i.scrollTop,n.top),P=o(i.scrollLeft,n.left),k=this.both?{rows:0,cols:0}:0,D=this.last,M=!1,Y=this.lastScrollPos;if(this.both){let c=this.lastScrollPos.top<=d,u=this.lastScrollPos.left<=P;if(!this._appendOnly||this._appendOnly&&(c||u)){let y={rows:r(d,this._itemSize[0]),cols:r(P,this._itemSize[1])},q={rows:l(y.rows,this.first.rows,this.last.rows,this.numItemsInViewport.rows,this.d_numToleratedItems[0],c),cols:l(y.cols,this.first.cols,this.last.cols,this.numItemsInViewport.cols,this.d_numToleratedItems[1],u)};k={rows:g(y.rows,q.rows,this.first.rows,this.last.rows,this.numItemsInViewport.rows,this.d_numToleratedItems[0],c),cols:g(y.cols,q.cols,this.first.cols,this.last.cols,this.numItemsInViewport.cols,this.d_numToleratedItems[1],u)},D={rows:f(y.rows,k.rows,this.last.rows,this.numItemsInViewport.rows,this.d_numToleratedItems[0]),cols:f(y.cols,k.cols,this.last.cols,this.numItemsInViewport.cols,this.d_numToleratedItems[1],!0)},M=k.rows!==this.first.rows||D.rows!==this.last.rows||k.cols!==this.first.cols||D.cols!==this.last.cols||this.isRangeChanged,Y={top:d,left:P}}}else{let c=this.horizontal?P:d,u=this.lastScrollPos<=c;if(!this._appendOnly||this._appendOnly&&u){let y=r(c,this._itemSize),q=l(y,this.first,this.last,this.numItemsInViewport,this.d_numToleratedItems,u);k=g(y,q,this.first,this.last,this.numItemsInViewport,this.d_numToleratedItems,u),D=f(y,k,this.last,this.numItemsInViewport,this.d_numToleratedItems),M=k!==this.first||D!==this.last||this.isRangeChanged,Y=c}}return{first:k,last:D,isRangeChanged:M,scrollPos:Y}}onScrollChange(e){let{first:i,last:n,isRangeChanged:o,scrollPos:r}=this.onScrollPositionChange(e);if(o){let l={first:i,last:n};if(this.setContentPosition(l),this.first=i,this.last=n,this.lastScrollPos=r,this.handleEvents("onScrollIndexChange",l),this._lazy&&this.isPageChanged(i)){let g={first:this._step?Math.min(this.getPageByFirst(i)*this._step,this.items.length-this._step):i,last:Math.min(this._step?(this.getPageByFirst(i)+1)*this._step:n,this.items.length)};(this.lazyLoadState.first!==g.first||this.lazyLoadState.last!==g.last)&&this.handleEvents("onLazyLoad",g),this.lazyLoadState=g}}}onContainerScroll(e){if(this.handleEvents("onScroll",{originalEvent:e}),this._delay&&this.isPageChanged()){if(this.scrollTimeout&&clearTimeout(this.scrollTimeout),!this.d_loading&&this.showLoader){let{isRangeChanged:i}=this.onScrollPositionChange(e);(i||(this._step?this.isPageChanged():!1))&&(this.d_loading=!0,this.cd.detectChanges())}this.scrollTimeout=setTimeout(()=>{this.onScrollChange(e),this.d_loading&&this.showLoader&&(!this._lazy||this._loading===void 0)&&(this.d_loading=!1,this.page=this.getPageByFirst()),this.cd.detectChanges()},this._delay)}else!this.d_loading&&this.onScrollChange(e)}bindResizeListener(){Oe(this.platformId)&&(this.windowResizeListener||this.zone.runOutsideAngular(()=>{let e=this.document.defaultView,i=ve()?"orientationchange":"resize";this.windowResizeListener=this.renderer.listen(e,i,this.onWindowResize.bind(this))}))}unbindResizeListener(){this.windowResizeListener&&(this.windowResizeListener(),this.windowResizeListener=null)}onWindowResize(){this.resizeTimeout&&clearTimeout(this.resizeTimeout),this.resizeTimeout=setTimeout(()=>{if(it(this.elementViewChild?.nativeElement)){let[e,i]=[_e(this.elementViewChild?.nativeElement),ye(this.elementViewChild?.nativeElement)],[n,o]=[e!==this.defaultWidth,i!==this.defaultHeight];(this.both?n||o:this.horizontal?n:this.vertical?o:!1)&&this.zone.run(()=>{this.d_numToleratedItems=this._numToleratedItems,this.defaultWidth=e,this.defaultHeight=i,this.defaultContentWidth=_e(this.contentEl),this.defaultContentHeight=ye(this.contentEl),this.init()})}},this._resizeDelay)}handleEvents(e,i){return this.options&&this.options[e]?this.options[e](i):this[e].emit(i)}getContentOptions(){return{contentStyleClass:`p-virtualscroller-content ${this.d_loading?"p-virtualscroller-loading":""}`,items:this.loadedItems,getItemOptions:e=>this.getOptions(e),loading:this.d_loading,getLoaderOptions:(e,i)=>this.getLoaderOptions(e,i),itemSize:this._itemSize,rows:this.loadedRows,columns:this.loadedColumns,spacerStyle:this.spacerStyle,contentStyle:this.contentStyle,vertical:this.vertical,horizontal:this.horizontal,both:this.both}}getOptions(e){let i=(this._items||[]).length,n=this.both?this.first.rows+e:this.first+e;return{index:n,count:i,first:n===0,last:n===i-1,even:n%2===0,odd:n%2!==0}}getLoaderOptions(e,i){let n=this.loaderArr.length;return W({index:e,count:n,first:e===0,last:e===n-1,even:e%2===0,odd:e%2!==0},i)}static \u0275fac=function(i){return new(i||t)(me(Be))};static \u0275cmp=x({type:t,selectors:[["p-scroller"],["p-virtualscroller"],["p-virtual-scroller"],["p-virtualScroller"]],contentQueries:function(i,n,o){if(i&1&&(B(o,Gt,4),B(o,Ui,4),B(o,Zi,4),B(o,qi,4),B(o,pe,4)),i&2){let r;T(r=I())&&(n.contentTemplate=r.first),T(r=I())&&(n.itemTemplate=r.first),T(r=I())&&(n.loaderTemplate=r.first),T(r=I())&&(n.loaderIconTemplate=r.first),T(r=I())&&(n.templates=r)}},viewQuery:function(i,n){if(i&1&&(we(Ki,5),we(Gt,5)),i&2){let o;T(o=I())&&(n.elementViewChild=o.first),T(o=I())&&(n.contentViewChild=o.first)}},hostVars:2,hostBindings:function(i,n){i&2&&Ve("height",n.height)},inputs:{id:"id",style:"style",styleClass:"styleClass",tabindex:"tabindex",items:"items",itemSize:"itemSize",scrollHeight:"scrollHeight",scrollWidth:"scrollWidth",orientation:"orientation",step:"step",delay:"delay",resizeDelay:"resizeDelay",appendOnly:"appendOnly",inline:"inline",lazy:"lazy",disabled:"disabled",loaderDisabled:"loaderDisabled",columns:"columns",showSpacer:"showSpacer",showLoader:"showLoader",numToleratedItems:"numToleratedItems",loading:"loading",autoSize:"autoSize",trackBy:"trackBy",options:"options"},outputs:{onLazyLoad:"onLazyLoad",onScroll:"onScroll",onScrollIndexChange:"onScrollIndexChange"},features:[V([Yt]),v,pt],ngContentSelectors:Gi,decls:3,vars:2,consts:[["disabledContainer",""],["element",""],["buildInContent",""],["content",""],["buildInLoader",""],["buildInLoaderIcon",""],[4,"ngIf","ngIfElse"],[3,"scroll","ngStyle","ngClass"],["class","p-virtualscroller-spacer",3,"ngStyle",4,"ngIf"],["class","p-virtualscroller-loader",3,"ngClass",4,"ngIf"],[4,"ngTemplateOutlet","ngTemplateOutletContext"],[3,"ngClass"],[4,"ngFor","ngForOf","ngForTrackBy"],[1,"p-virtualscroller-spacer",3,"ngStyle"],[1,"p-virtualscroller-loader",3,"ngClass"],[4,"ngFor","ngForOf"],[3,"styleClass"],[4,"ngIf"]],template:function(i,n){if(i&1&&(le(),_(0,_n,8,16,"ng-container",6)(1,Cn,2,1,"ng-template",null,0,fe)),i&2){let o=Ie(2);a("ngIf",!n._disabled)("ngIfElse",o)}},dependencies:[A,ce,Ct,Ae,de,xe,Vt,O],encapsulation:2})}return t})(),yr=(()=>{class t{static \u0275fac=function(i){return new(i||t)};static \u0275mod=j({type:t});static \u0275inj=H({imports:[xn,O,O]})}return t})();export{Do as a,Bo as b,Ro as c,jo as d,ts as e,gs as f,Os as g,ks as h,Wi as i,Gs as j,xn as k,yr as l,jt as m,so as n,Si as o,vo as p,Qt as q};
