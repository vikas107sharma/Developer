
let arr = [1,2,3,4,5]

// FILTER
Array.prototype.myFilter = function(cb){
    const res = []
    for(let i=0;i<this.length; i++) {
        if(cb(this[i], i, this)) {
            res.push(this[i]);
        }
    }
    return res;
}
console.log(arr.myFilter((e)=> e>2));    // res.push(cb(this[i]));
console.log(arr.myFilter((e, i)=> e+i>2)); // res.push(cb(this[i], i));


// MAP
Array.prototype.myMap = function(cb) {
    const res = []
    for(let i = 0; i<arr.length; i++) {
        res.push(cb(this[i], i , this));
    }
    return res
}
console.log(arr.myMap((e)=> e*2));    // res.push(cb(this[i]));
console.log(arr.myMap((e, i)=> e*i)); // res.push(cb(this[i], i));


